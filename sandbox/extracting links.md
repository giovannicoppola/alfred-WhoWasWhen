To separate the text and the underlying links from a column in a Google Sheets where cells contain formatted hyperlinks, you can use Google Apps Script to extract this information into two separate columns. 

Here’s how you can achieve this:

1. **Open Google Sheets** and go to `Extensions` > `Apps Script`.

2. **Paste the following script** into the script editor:

    ```javascript
    function extractHyperlinks() {
        // Open the active spreadsheet and select the active sheet
        var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
        // Define the range to process (for example, the first column)
        var range = sheet.getRange("A2:A" + sheet.getLastRow());  // Adjust range as needed
        var values = range.getValues();
        var richTextValues = range.getRichTextValues();
        
        var textColumn = [];
        var linkColumn = [];

        for (var i = 0; i < values.length; i++) {
            var richTextValue = richTextValues[i][0];
            var text = richTextValue.getText();
            var link = richTextValue.getLinkUrl(0); // Assuming single hyperlink per cell
            
            textColumn.push([text]);
            linkColumn.push([link ? link : ""]); // Check if link exists
        }

        // Write the extracted text and links to new columns
        sheet.getRange(2, 2, textColumn.length, 1).setValues(textColumn); // Column B
        sheet.getRange(2, 3, linkColumn.length, 1).setValues(linkColumn); // Column C
    }
    ```

3. **Adjust the Range**: Modify the range in `getRange("A2:A" + sheet.getLastRow())` if your data starts from a different cell or column. This example assumes your hyperlinks are in column `A` starting from row `2`.

4. **Save the script**: Give it a name, like `ExtractHyperlinks`.

5. **Run the script**:
    - Click the play button ▶️ in the script editor to run the function.
    - You may need to authorize the script to access your Google Sheets.

6. **Check your sheet**: The script will place the text in column `B` and the links in column `C`.

### How the Script Works

- **Range Selection**: It selects the range of cells you specify which contain the hyperlinks.
- **Rich Text Extraction**: It extracts the rich text and the hyperlinks from the cells.
- **Splitting Text and Links**: It separates the text and the link for each cell.
- **Writing Results**: It writes the separated text and links into new columns (`B` for text and `C` for links).

### Example Sheet

Here’s how your Google Sheet might look after running the script:

| A               | B             | C              |
|-----------------|---------------|----------------|
| Hyperlinked Text| Text Only     | Link Only      |
| Click here      | Click here    | https://example.com |
| Visit our site  | Visit our site| https://example.org |

### Notes
- This script assumes there is only one hyperlink per cell. If a cell contains multiple hyperlinks, you may need a more complex script.
- If your hyperlinks are not formatted as expected, verify that the `getLinkUrl` method accurately reflects your hyperlink structure.

### Example

Let’s say your Google Sheet has the following in column A:
- `A1`: "Hyperlinked Text"
- `A2`: `Click here` (with the hyperlink pointing to `https://example.com`)
- `A3`: `Visit our site` (with the hyperlink pointing to `https://example.org`)

After running the script:
- `B2`: `Click here`
- `C2`: `https://example.com`
- `B3`: `Visit our site`
- `C3`: `https://example.org`