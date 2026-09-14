package main

import (
	"encoding/csv"
	"fmt"
	"net/http"
	"strings"
)

// getSheet retrieves data from a public Google Sheet via CSV export
func getSheet(spreadsheetID, sheetName string, selectedColumns []string) ([][]string, error) {
	// Map sheet names to their correct GIDs
	sheetGIDs := map[string]string{
		"Periods": "0",
		"Rulers":  "2053495317",
		"Events":  "877936494",
	}

	gid, exists := sheetGIDs[sheetName]
	if !exists {
		return nil, fmt.Errorf("unknown sheet name: %s", sheetName)
	}

	// Build CSV export URL
	csvURL := fmt.Sprintf("https://docs.google.com/spreadsheets/d/%s/export?format=csv&gid=%s", spreadsheetID, gid)

	// Create HTTP client that follows redirects
	client := &http.Client{}

	// Create request with proper headers
	req, err := http.NewRequest("GET", csvURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Add User-Agent header to avoid redirect issues
	req.Header.Set("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

	// Fetch CSV data
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch CSV: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("failed to fetch CSV: HTTP %d", resp.StatusCode)
	}

	// Parse CSV
	reader := csv.NewReader(resp.Body)
	allRecords, err := reader.ReadAll()
	if err != nil {
		return nil, fmt.Errorf("failed to parse CSV: %w", err)
	}

	if len(allRecords) == 0 {
		return nil, fmt.Errorf("no data found in sheet %s", sheetName)
	}

	// Filter data to include only selected columns
	filteredData, err := filterColumns(allRecords, selectedColumns)
	if err != nil {
		return nil, fmt.Errorf("error filtering columns: %w", err)
	}

	return filteredData, nil
}

// filterColumns filters the data to include only selected columns
func filterColumns(allValues [][]string, selectedColumns []string) ([][]string, error) {
	if len(allValues) == 0 {
		return nil, fmt.Errorf("no data to filter")
	}

	headers := allValues[0]
	var columnIndices []int

	// Find indices of selected columns
	for _, col := range selectedColumns {
		found := false
		for i, header := range headers {
			if strings.TrimSpace(header) == col {
				columnIndices = append(columnIndices, i)
				found = true
				break
			}
		}
		if !found {
			logMessage("Warning: Column '%s' not found in headers", col)
			columnIndices = append(columnIndices, -1)
		}
	}

	// Filter data
	var filteredData [][]string

	// Add header row
	filteredData = append(filteredData, selectedColumns)

	// Filter data rows
	for i := 1; i < len(allValues); i++ {
		row := allValues[i]
		var filteredRow []string

		for _, colIndex := range columnIndices {
			if colIndex >= 0 && colIndex < len(row) {
				filteredRow = append(filteredRow, strings.TrimSpace(row[colIndex]))
			} else {
				filteredRow = append(filteredRow, "")
			}
		}

		// Skip completely empty rows
		isEmpty := true
		for _, cell := range filteredRow {
			if cell != "" {
				isEmpty = false
				break
			}
		}
		if isEmpty {
			continue
		}

		filteredData = append(filteredData, filteredRow)
	}

	return filteredData, nil
}
