"""Decides which parts of the film to keep, from what the film shows rather than from the log.

The tour script's log says *when it meant* to act, but XCUITest can stall for seconds finding an
element, before or after the logged moment, with nothing moving on screen. So this reads the film:
every stretch where the screen moves is kept at full speed, and the still stretches are trimmed so
each scene lasts as long as its narration line needs. Touch rings go where the screen starts to
answer a touch, not where the log says the touch was asked for.

Usage: python3 plan.py <recording dir> <narration dir>   -> writes <recording dir>/plan.json
Needs ffmpeg and numpy.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

FPS = 30
W, H = 114, 248  # a sixth of screen.mp4: plenty to see motion
STILL = 0.4      # shorter pauses than this are part of the motion around them
SETTLE = 0.35    # every kept still stretch shows at least this much of itself
LEAD, TAIL = 0.25, 0.65  # a line starts a beat after its caption, and ends before the next

rec, voice = Path(sys.argv[1]), Path(sys.argv[2])
events = json.loads((rec / 'events.json').read_text())

raw = subprocess.run(
    ['ffmpeg', '-v', 'error', '-i', rec / 'screen.mp4', '-vf', f'scale={W}:{H},format=gray', '-f', 'rawvideo', '-'],
    check=True, capture_output=True).stdout
frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.int16)
# Ignore the status bar: its clock is pinned, but the simulator still redraws it now and then.
mask = np.ones((H, W), bool)
mask[: int(H * 0.07)] = False
diff = np.abs(frames[1:] - frames[:-1])[:, mask].mean(axis=1)
moving = np.concatenate([[False], diff > 0.6])

# Still runs, as [start, end) in seconds.
runs, start = [], None
for i, m in enumerate(list(moving) + [True]):
    if not m and start is None:
        start = i
    elif m and start is not None:
        if (i - start) / FPS >= STILL:
            runs.append([start / FPS, i / FPS])
        start = None

captions = [e for e in events if e['type'] == 'caption']
end = next(e['t'] for e in events if e['type'] == 'end')
bounds = [c['t'] for c in captions] + [end]
lines = sorted(voice.glob('line-*.wav'))
if len(lines) != len(captions) + 1:
    sys.exit(f'{len(lines)} narration lines for {len(captions)} captions and the end card')
need = [sf.info(p).duration + LEAD + TAIL for p in lines]

# Per scene: keep all motion, then share what the line still needs among its still runs.
keep = []  # [source start, source end]
for k in range(len(captions)):
    a, b = bounds[k], bounds[k + 1]
    stills = [[max(s, a), min(e, b)] for s, e in runs if e > a and s < b]
    stills = [s for s in stills if s[1] - s[0] > 0.05]
    still_total = sum(e - s for s, e in stills)
    motion = (b - a) - still_total
    budget = max(need[k] - motion, SETTLE * len(stills))
    # Every pause gets a moment to settle; the rest goes to the scene's last still first, since
    # that is the state its caption and line describe (the chart drawn, the calendar open), and
    # the earlier stills are mostly the runner looking for the next button.
    share = {(s, e): min(e - s, SETTLE) for s, e in stills}
    left = budget - sum(share.values())
    for s, e in reversed(stills):
        extra = min(max(left, 0), (e - s) - share[(s, e)])
        share[(s, e)] += extra
        left -= extra
    cursor = a
    for s, e in stills:
        keep.append([cursor, s + share[(s, e)]])
        cursor = e
    keep.append([cursor, b])

# Merge touching pieces.
merged = []
for s, e in keep:
    if e - s < 1 / FPS:
        continue
    if merged and abs(merged[-1][1] - s) < 1e-6:
        merged[-1][1] = e
    else:
        merged.append([s, e])


def to_output(t):
    """Where a moment of the film lands in the cut; a trimmed moment lands where its piece ends."""
    out = 0.0
    for s, e in merged:
        if t < s:
            return out
        if t <= e:
            return out + (t - s)
        out += e - s
    return out


def onset(t, within=8.0):
    """The first frame moving after t: when the screen answered the touch logged at t."""
    i0 = int(t * FPS)
    for i in range(i0, min(len(moving), i0 + int(within * FPS))):
        if moving[i]:
            return i / FPS
    return t + 0.3


touches = []
for e in events:
    if e['type'] in ('tap', 'swipe'):
        # Shown from just before the screen answers until it starts to, so the ring leads the reaction.
        at = to_output(onset(e['t'])) - 0.4
        touches.append({**e, 't': round(max(at, 0), 3)})

plan = {
    'keep': [[round(s, 3), round(e, 3)] for s, e in merged],
    'captions': [{**c, 't': round(to_output(c['t']), 3)} for c in captions],
    'touches': touches,
    'end': round(to_output(end), 3),
}
(rec / 'plan.json').write_text(json.dumps(plan, indent=1, ensure_ascii=False))
scenes = [c['t'] for c in plan['captions']] + [plan['end']]
for k, c in enumerate(plan['captions']):
    print(f"{scenes[k]:5.1f}s  {scenes[k + 1] - scenes[k]:4.1f}s (needs {need[k]:3.1f})  {c['title']}")
print(f"{plan['end']:5.1f}s  end card; {len(merged)} pieces kept from {len(frames) / FPS:.0f}s of film")
