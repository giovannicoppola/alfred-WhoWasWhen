# WhoWasWhen Go - Installation Guide

## Basic Installation

1. Double-click the `.alfredworkflow` file
2. Alfred will open and prompt you to import the workflow
3. Click "Import" to add it to your workflows

## Google Sheets Setup

To use your own Google Sheet as a data source:

1. Create a Google Sheet with two tabs: "Rulers" and "Periods"
2. Format the "Rulers" sheet with columns:
   - RulerID (integer)
   - Name
   - Personal Name
   - Wikipedia (URL)
   - Epithet
   - Notes

3. Format the "Periods" sheet with columns:
   - Title (e.g., "Pope", "English Monarch")
   - RulerID (matching the Rulers sheet)
   - Period (e.g., "1509-1547", "44BC")
   - Notes

4. Set up Google API credentials:
   - Create a project in the Google Developer Console
   - Enable the Google Sheets API
   - Create a service account
   - Download the JSON key file

5. Share your Google Sheet with the service account's email address

6. Edit the `config.py` file to update:
   - `KEYFILE`: Path to your Google API service account JSON key file
   - `GSHEET_URL`: URL of your Google Sheet

## Workflow Configuration

You can customize the following aspects:

1. Database location: Edit the `DATA_FOLDER` in `config.py`
2. Refresh keyword: Change through Alfred's workflow configuration

## Troubleshooting

### Database not generating:
- Check your Google API service account key file path
- Verify the Google Sheet is shared with the service account
- Check Alfred's console logs for errors

### Search not working:
- Make sure the database was generated successfully
- Check permissions on the database file
- Try running the refresh command

## Manual Database Generation

If needed, you can manually generate the database:

```bash
cd /path/to/workflow
./whowaswhen.py --alfred
```

## Keeping Your Database Updated

Set up a periodic refresh of your database if your Google Sheet changes frequently:

1. Use Alfred's built-in triggers to run the refresh command periodically
2. Or use a system cron job to run the script 