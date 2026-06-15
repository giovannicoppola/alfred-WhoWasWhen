# WhoWasWhen — Google Sheet maintenance

Scripts and patches for the **master Google Spreadsheet** used by the Alfred WhoWasWhen workflow.

**Agents:** read [AGENT_INSTRUCTIONS.md](AGENT_INSTRUCTIONS.md) first.

## Quick start

```bash
cd sheet-maintenance
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Same service account JSON as alfred-gsheets → Workflow Configuration → Key File
export KEYFILE="/path/to/service-account.json"

python apply_merged_ruler_patches.py --discover
python audit_merged_rulers.py
python apply_merged_ruler_patches.py --dry-run --tier E
python apply_merged_ruler_patches.py --apply --tier E

# Events
python add_events.py --list --query "thirty years"
python add_events.py --dry-run --file patches/events/thirty-years-war-battles.yaml
python add_events.py --apply --file patches/events/thirty-years-war-battles.yaml
```

Share the spreadsheet with the service account email as **Editor**.

Copy `config.example.yaml` → `config.yaml` if you prefer a file over `KEYFILE`.

After sheet changes, rebuild the Alfred database: `::whoWasWhen-refresh`.

## Files

| File | Purpose |
|------|---------|
| `apply_merged_ruler_patches.py` | Apply fixes from `patches/merged-rulers.yaml` |
| `add_events.py` | Append events from `patches/events/*.yaml` |
| `audit_event_duplicates.py` | Find duplicate Events rows (year-aware) |
| `merge_event_duplicates.py` | Merge duplicates: enrich keeper, delete extras |
| `audit_merged_rulers.py` | Find likely merged-ruler bugs |
| `patches/merged-rulers.yaml` | Versioned patch definitions |
| `AGENT_INSTRUCTIONS.md` | Full agent maintenance playbook |
