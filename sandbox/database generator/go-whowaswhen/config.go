package main

import (
	"fmt"
	"os"
	"path/filepath"
)

// workflowBundleID matches the bundleid in source/info.plist; it only names
// the fallback data folder used when Alfred has not set alfred_workflow_data.
const workflowBundleID = "giovanni-whowaswhen"

// getConfig initializes and returns configuration with default values
func getConfig() *Config {
	// Determine data folder. Alfred sets alfred_workflow_data; honour it
	// whatever it points at. An earlier version only accepted paths
	// containing "giovanni-whowaswhen" and otherwise fell back to a
	// hardcoded path under the developer's home — which meant any run with a
	// differently-named data folder silently wrote to that one instead.
	dataFolder := os.Getenv("alfred_workflow_data")
	if dataFolder == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			home = "/Users/giovanni"
		}
		dataFolder = filepath.Join(home, "Library/Application Support/Alfred/Workflow Data", workflowBundleID)
	}

	// Create data folder if it doesn't exist
	if _, err := os.Stat(dataFolder); os.IsNotExist(err) {
		os.MkdirAll(dataFolder, 0755)
	}

	fmt.Fprintf(os.Stderr, "Data folder: %s\n", dataFolder)

	// Default configuration values
	config := &Config{
		DataFolder:    dataFolder,
		GSheetURL:     "https://docs.google.com/spreadsheets/d/1GKI1744hxSBmB75CrIYssK6Y8-Hd48kpaggvOG1kUM8/edit?usp=sharing",
		PeriodSheet:   "Periods",
		RulersSheet:   "Rulers",
		DatabaseName:  filepath.Join(dataFolder, "whoWasWhen.db"),
		SpreadsheetID: "1GKI1744hxSBmB75CrIYssK6Y8-Hd48kpaggvOG1kUM8",
	}

	return config
}
