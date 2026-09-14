package main

import (
	"encoding/csv"
	"fmt"
	"os"
)

// readFromTSV reads data from a TSV file and returns it as a slice of string slices
func readFromTSV(filename string, expectedColumns []string) ([][]string, error) {
	file, err := os.Open(filename)
	if err != nil {
		return nil, err // Don't log error - file may not exist, which is normal now
	}
	defer file.Close()

	reader := csv.NewReader(file)
	reader.Comma = '\t' // Set delimiter to tab for TSV

	records, err := reader.ReadAll()
	if err != nil {
		return nil, fmt.Errorf("failed to read TSV file %s: %w", filename, err)
	}

	if len(records) == 0 {
		return nil, fmt.Errorf("TSV file %s is empty", filename)
	}

	// Verify headers match expected columns
	headers := records[0]
	if len(headers) != len(expectedColumns) {
		logMessage("Warning: Headers in %s don't match expected columns", filename)
		logMessage("Expected: %v", expectedColumns)
		logMessage("Found: %v", headers)
	}

	logMessage("Data loaded from %s", filename)
	return records, nil
}
