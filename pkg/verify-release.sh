#!/bin/bash
# Preflight for a WhoWasWhen release. Run against source/ (or an unpacked
# .alfredworkflow) BEFORE shipping.
#
# Exists because v0.4 shipped `whowaswhen` as a second copy of `ruler-query`.
# The workflow has no database: ruler-query execs its sibling `whowaswhen` to
# build one on first run, so a `whowaswhen` that is really ruler-query execs
# itself without bound. Both binaries are signed under their own name, so
# codesign/spctl pass and the mistake is invisible.
#
# Do NOT identify the builder by "database created successfully" — ruler-query
# also embeds that literal, in the guard that checks the child's output.

set -u
DIR="${1:-source}"
fail=0
note() { printf '  %-34s %s\n' "$1" "$2"; }

for b in ruler-query whowaswhen; do
	[ -f "$DIR/$b" ] || { echo "MISSING: $DIR/$b"; fail=1; continue; }
done
[ "$fail" = 1 ] && exit 1

echo "Checking $DIR"

# 1. The two binaries must be different programs.
if [ "$(md5 -q "$DIR/ruler-query")" = "$(md5 -q "$DIR/whowaswhen")" ]; then
	note "distinct binaries" "FAIL (identical files)"; fail=1
else
	note "distinct binaries" "ok"
fi

# 2. whowaswhen must be the DB generator, ruler-query must not be.
if strings -a "$DIR/whowaswhen" | grep -q "Fetching data from public Google Sheets"; then
	note "whowaswhen is the DB builder" "ok"
else
	note "whowaswhen is the DB builder" "FAIL (it is not the generator)"; fail=1
fi
if strings -a "$DIR/ruler-query" | grep -q "Fetching data from public Google Sheets"; then
	note "ruler-query is the querier" "FAIL (it is the generator)"; fail=1
else
	note "ruler-query is the querier" "ok"
fi

# 3. The builder must emit the born/died columns the querier selects.
if strings -a "$DIR/whowaswhen" | grep -q "biography, born, died"; then
	note "builder writes born/died" "ok"
else
	note "builder writes born/died" "FAIL (stale builder; r.born will not exist)"; fail=1
fi

# 4. The querier must carry the exec-recursion guard.
if strings -a "$DIR/ruler-query" | grep -q "WHOWASWHEN_UPDATE_CHILD"; then
	note "recursion guard present" "ok"
else
	note "recursion guard present" "FAIL (a mis-packaged build could fork bomb)"; fail=1
fi

# 5. Universal (amd64 + arm64). build.sh lipo's the two slices together; a
#    binary built for only one arch runs on half the user base.
for b in ruler-query whowaswhen; do
	archs=$(lipo -archs "$DIR/$b" 2>/dev/null)
	missing=""
	for a in x86_64 arm64; do
		case " $archs " in *" $a "*) ;; *) missing="$missing $a" ;; esac
	done
	if [ -z "$missing" ]; then
		note "$b universal" "ok ($archs)"
	else
		note "$b universal" "FAIL (missing:$missing; have: ${archs:-none})"; fail=1
	fi
done

# 6. Signature on EVERY slice, not just the fat header. lipo strips the arm64
#    ad-hoc signature, so a binary signed before lipo leaves arm64 unsigned
#    while `codesign -dvv` on the fat file still looks fine. Sign after lipo.
for b in ruler-query whowaswhen; do
	for a in $(lipo -archs "$DIR/$b" 2>/dev/null); do
		if ! codesign --verify --strict --arch "$a" "$DIR/$b" >/dev/null 2>&1; then
			note "$b $a signature" "FAIL (does not verify)"; fail=1; continue
		fi
		d=$(codesign -dvv --arch "$a" "$DIR/$b" 2>&1)
		case "$d" in
			*"Authority=Developer ID Application: Giovanni Coppola (VDG762YNX9)"*) ;;
			*) note "$b $a signature" "FAIL (not Developer ID signed)"; fail=1; continue ;;
		esac
		case "$d" in
			*"flags=0x10000(runtime)"*) ;;
			*) note "$b $a signature" "FAIL (no hardened runtime; blocks notarization)"; fail=1; continue ;;
		esac
		note "$b $a signature" "ok (Developer ID + runtime)"
	done
done

# 7. Gatekeeper: a downloaded .alfredworkflow is quarantined, and an
#    un-notarized binary is blocked with no visible error in Alfred.
for b in ruler-query whowaswhen; do
	if spctl -a -t install "$DIR/$b" >/dev/null 2>&1; then
		note "$b notarized" "ok"
	else
		note "$b notarized" "FAIL (would be blocked on download)"; fail=1
	fi
done

[ "$fail" = 0 ] && echo "PASS" || echo "FAILED — do not ship"
exit $fail
