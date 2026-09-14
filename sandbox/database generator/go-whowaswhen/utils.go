package main

import (
	"archive/zip"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"time"
)

// createZippedDatabase creates a zipped version of the database
func createZippedDatabase(dbName string) error {
	// Get the base name of the database file
	dbBaseName := filepath.Base(dbName)

	// Create zip filename in the same directory as the database
	zipFilename := dbName + ".zip"

	logMessage("Creating zipped database '%s'...", zipFilename)
	zipStartTime := time.Now()

	// Create the zip file
	zipFile, err := os.Create(zipFilename)
	if err != nil {
		return fmt.Errorf("failed to create zip file: %w", err)
	}
	defer zipFile.Close()

	// Create a new zip writer
	zipWriter := zip.NewWriter(zipFile)
	defer zipWriter.Close()

	// Open the database file
	dbFile, err := os.Open(dbName)
	if err != nil {
		return fmt.Errorf("failed to open database file: %w", err)
	}
	defer dbFile.Close()

	// Create a file in the zip with just the base name
	zipEntry, err := zipWriter.Create(dbBaseName)
	if err != nil {
		return fmt.Errorf("failed to create zip entry: %w", err)
	}

	// Copy the database file to the zip entry
	_, err = io.Copy(zipEntry, dbFile)
	if err != nil {
		return fmt.Errorf("failed to copy database to zip: %w", err)
	}

	zipTime := time.Since(zipStartTime)
	logMessage("Zipped database created in %.3f seconds", zipTime.Seconds())

	return nil
}
