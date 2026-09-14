package main

import (
	"database/sql"
	"fmt"
	"strconv"
	"strings"
)

// populateRulers populates the rulers table in the database
func populateRulers(allRulers [][]string, dbName string) error {
	db, err := sql.Open("sqlite3", dbName)
	if err != nil {
		return fmt.Errorf("failed to open database: %w", err)
	}
	defer db.Close()

	// Drop table if it exists
	_, err = db.Exec("DROP TABLE IF EXISTS rulers")
	if err != nil {
		return fmt.Errorf("failed to drop rulers table: %w", err)
	}

	// Create the rulers table
	createTableSQL := `
	CREATE TABLE IF NOT EXISTS rulers (
		rulerID INTEGER PRIMARY KEY,
		name TEXT,
		personal_name TEXT,
		epithet TEXT,
		wikipedia TEXT,
		notes TEXT,
		biography TEXT,
		born INTEGER,
		died INTEGER
	)`
	_, err = db.Exec(createTableSQL)
	if err != nil {
		return fmt.Errorf("failed to create rulers table: %w", err)
	}

	// Prepare insert statement
	insertSQL := `
	INSERT OR IGNORE INTO rulers (
		rulerID, name, personal_name, epithet, wikipedia, notes, biography, born, died
	) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
	stmt, err := db.Prepare(insertSQL)
	if err != nil {
		return fmt.Errorf("failed to prepare insert statement: %w", err)
	}
	defer stmt.Close()

	skippedCount := 0
	for i, row := range allRulers {
		if i == 0 {
			// Skip header row
			continue
		}

		// Ensure row has enough columns
		for len(row) < 8 {
			row = append(row, "")
		}

		// Skip rows where RulerID is empty, null, or not a valid number
		rulerIDStr := strings.TrimSpace(row[0])
		if rulerIDStr == "" {
			skippedCount++
			skippedRows++ // Global counter
			logMessage("Skipping row with empty RulerID: %s", getValueOrDefault(row, 1, "Unknown"))
			continue
		}

		rulerID, err := strconv.Atoi(rulerIDStr)
		if err != nil {
			skippedCount++
			skippedRows++ // Global counter
			logMessage("Skipping row with invalid RulerID '%s': %s", rulerIDStr, getValueOrDefault(row, 1, "Unknown"))
			continue
		}

		born := parseOptionalInt(getValueOrDefault(row, 6, ""))
		died := parseOptionalInt(getValueOrDefault(row, 7, ""))

		_, err = stmt.Exec(
			rulerID,
			getValueOrDefault(row, 1, ""), // Name
			getValueOrDefault(row, 2, ""), // Personal Name
			getValueOrDefault(row, 4, ""), // Epithet
			getValueOrDefault(row, 3, ""), // Wikipedia
			getValueOrDefault(row, 5, ""), // Notes
			"",                            // Biography will be generated later
			born,
			died,
		)
		if err != nil {
			return fmt.Errorf("failed to insert ruler: %w", err)
		}
	}

	if skippedCount > 0 {
		logMessage("Rulers table successfully exported to SQLite database (skipped %d rows with invalid RulerID)", skippedCount)
	} else {
		logMessage("Rulers table successfully exported to SQLite database")
	}

	return nil
}

// populateTables populates the titles, years, byPeriod, and byYear tables in the database
func populateTables(allPeriods [][]string, dbName string) error {
	db, err := sql.Open("sqlite3", dbName)
	if err != nil {
		return fmt.Errorf("failed to open database: %w", err)
	}
	defer db.Close()

	// Enable faster inserts
	db.Exec("PRAGMA synchronous = OFF")
	db.Exec("PRAGMA journal_mode = MEMORY")

	// Create tables
	err = createTables(db)
	if err != nil {
		return fmt.Errorf("failed to create tables: %w", err)
	}

	// Collect all unique titles and years first
	titles := make(map[string]bool)
	allYears := make(map[int]bool)
	var periodsData []periodData
	titleCheck := make(map[string]int)

	// First pass - collect data
	for i, row := range allPeriods {
		if i == 0 {
			// Skip header row
			continue
		}

		// Ensure row has enough columns
		for len(row) < 4 {
			row = append(row, "")
		}

		// Validate and clean the period field first
		periodRaw := strings.TrimSpace(getValueOrDefault(row, 2, ""))
		if periodRaw == "" {
			skippedRows++ // Global counter
			logMessage("Skipping row with empty Period for title '%s', RulerID '%s'",
				getValueOrDefault(row, 0, ""), getValueOrDefault(row, 1, ""))
			continue
		}

		// Attempt to parse the period
		startYear, endYear, err := parsePeriod(periodRaw)
		if err != nil {
			skippedRows++ // Global counter
			logMessage("Skipping row with invalid Period '%s' for title '%s', RulerID '%s': %v",
				periodRaw, getValueOrDefault(row, 0, ""), getValueOrDefault(row, 1, ""), err)
			continue
		}

		title := getValueOrDefault(row, 0, "")
		rulerIDStr := strings.TrimSpace(getValueOrDefault(row, 1, ""))

		if rulerIDStr == "" {
			skippedRows++ // Global counter
			logMessage("Skipping row with empty RulerID for title '%s'", title)
			continue
		}

		rulerID, err := strconv.Atoi(rulerIDStr)
		if err != nil {
			skippedRows++ // Global counter
			logMessage("Skipping row with invalid RulerID '%s' for title '%s'", rulerIDStr, title)
			continue
		}

		titles[title] = true
		titleCheck[title]++

		// Add years to the set
		for year := startYear; year <= endYear; year++ {
			allYears[year] = true
		}

		periodsData = append(periodsData, periodData{
			title:      title,
			rulerID:    rulerID,
			period:     periodRaw,
			startYear:  startYear,
			endYear:    endYear,
			notes:      getValueOrDefault(row, 3, ""),
			progrTitle: titleCheck[title],
		})
	}

	// Batch insert titles and get mappings
	titleMappings, err := batchInsertTitles(db, titles)
	if err != nil {
		return fmt.Errorf("failed to insert titles: %w", err)
	}

	// Batch insert years and get mappings
	yearMappings, err := batchInsertYears(db, allYears)
	if err != nil {
		return fmt.Errorf("failed to insert years: %w", err)
	}

	// Batch insert periods
	err = batchInsertPeriods(db, periodsData, titleMappings)
	if err != nil {
		return fmt.Errorf("failed to insert periods: %w", err)
	}

	// Insert byYear data
	err = insertByYearData(db, yearMappings)
	if err != nil {
		return fmt.Errorf("failed to insert byYear data: %w", err)
	}

	// Update maxCount for titles
	err = updateTitleMaxCounts(db, titleCheck)
	if err != nil {
		return fmt.Errorf("failed to update title max counts: %w", err)
	}

	// Update plurals
	err = updateTitlePlurals(db)
	if err != nil {
		return fmt.Errorf("failed to update title plurals: %w", err)
	}

	logMessage("Titles and junction table successfully exported to SQLite database")
	return nil
}

// populateEvents populates the byEvents table in the database
func populateEvents(allEvents [][]string, dbName string) error {
	db, err := sql.Open("sqlite3", dbName)
	if err != nil {
		return fmt.Errorf("failed to open database: %w", err)
	}
	defer db.Close()

	// Enable faster inserts
	db.Exec("PRAGMA synchronous = OFF")
	db.Exec("PRAGMA journal_mode = MEMORY")

	// Drop table if it exists
	_, err = db.Exec("DROP TABLE IF EXISTS byEvents")
	if err != nil {
		return fmt.Errorf("failed to drop byEvents table: %w", err)
	}

	// Create the byEvents table. startMonth/startDay are NULL when the
	// sheet has no exact date (they feed the iOS app's "On this day").
	createTableSQL := `
	CREATE TABLE IF NOT EXISTS byEvents (
		eventID INTEGER PRIMARY KEY AUTOINCREMENT,
		eventName TEXT,
		startYear INTEGER,
		endYear INTEGER,
		notes TEXT,
		wikipedia TEXT,
		startMonth INTEGER,
		startDay INTEGER
	)`
	_, err = db.Exec(createTableSQL)
	if err != nil {
		return fmt.Errorf("failed to create byEvents table: %w", err)
	}

	// Collect all years and events data
	allYears := make(map[int]bool)
	var eventsData []eventData

	// Process events data
	for i, row := range allEvents {
		if i == 0 {
			// Skip header row
			continue
		}

		// Ensure row has enough columns
		for len(row) < 6 {
			row = append(row, "")
		}

		eventName := getValueOrDefault(row, 0, "")
		numericalYear := strings.TrimSpace(getValueOrDefault(row, 1, ""))
		notes := getValueOrDefault(row, 2, "")
		wikipedia := getValueOrDefault(row, 3, "")
		startMonth := parseOptionalInt(getValueOrDefault(row, 4, ""))
		startDay := parseOptionalInt(getValueOrDefault(row, 5, ""))

		// Skip empty rows
		if eventName == "" || numericalYear == "" {
			skippedRows++ // Global counter
			continue
		}

		startYear, endYear, err := parsePeriod(numericalYear)
		if err != nil {
			skippedRows++ // Global counter
			logMessage("Error parsing year '%s' for event '%s': %v", numericalYear, eventName, err)
			continue
		}

		// Add years to the set
		for year := startYear; year <= endYear; year++ {
			allYears[year] = true
		}

		eventsData = append(eventsData, eventData{
			eventName:  eventName,
			startYear:  startYear,
			endYear:    endYear,
			notes:      notes,
			wikipedia:  wikipedia,
			startMonth: startMonth,
			startDay:   startDay,
		})
	}

	// Insert years if they don't exist (reuse existing years table)
	if len(allYears) > 0 {
		stmt, err := db.Prepare("INSERT OR IGNORE INTO years (year) VALUES (?)")
		if err != nil {
			return fmt.Errorf("failed to prepare year insert statement: %w", err)
		}
		defer stmt.Close()

		for year := range allYears {
			_, err = stmt.Exec(year)
			if err != nil {
				return fmt.Errorf("failed to insert year: %w", err)
			}
		}
	}

	// Get year mappings
	yearMappings, err := getYearMappings(db, allYears)
	if err != nil {
		return fmt.Errorf("failed to get year mappings: %w", err)
	}

	// Insert events data
	stmt, err := db.Prepare(`
		INSERT INTO byEvents (eventName, startYear, endYear, notes, wikipedia, startMonth, startDay)
		VALUES (?, ?, ?, ?, ?, ?, ?)
	`)
	if err != nil {
		return fmt.Errorf("failed to prepare event insert statement: %w", err)
	}
	defer stmt.Close()

	for _, event := range eventsData {
		_, err = stmt.Exec(
			event.eventName,
			event.startYear,
			event.endYear,
			event.notes,
			event.wikipedia,
			event.startMonth,
			event.startDay,
		)
		if err != nil {
			return fmt.Errorf("failed to insert event: %w", err)
		}
	}

	// Get all eventIDs for linking to years
	rows, err := db.Query("SELECT eventID, startYear, endYear FROM byEvents")
	if err != nil {
		return fmt.Errorf("failed to query events: %w", err)
	}
	defer rows.Close()

	var eventRanges []struct {
		eventID   int
		startYear int
		endYear   int
	}

	for rows.Next() {
		var eventID, startYear, endYear int
		if err := rows.Scan(&eventID, &startYear, &endYear); err != nil {
			return fmt.Errorf("failed to scan event: %w", err)
		}
		eventRanges = append(eventRanges, struct {
			eventID   int
			startYear int
			endYear   int
		}{eventID, startYear, endYear})
	}

	// Add eventID column to byYear table if it doesn't exist
	err = addEventIDColumn(db)
	if err != nil {
		return fmt.Errorf("failed to add eventID column: %w", err)
	}

	// Insert byYear data for events
	stmt, err = db.Prepare("INSERT OR IGNORE INTO byYear (yearID, eventID) VALUES (?, ?)")
	if err != nil {
		return fmt.Errorf("failed to prepare byYear event insert statement: %w", err)
	}
	defer stmt.Close()

	for _, event := range eventRanges {
		for year := event.startYear; year <= event.endYear; year++ {
			if yearID, exists := yearMappings[year]; exists {
				_, err = stmt.Exec(yearID, event.eventID)
				if err != nil {
					return fmt.Errorf("failed to insert byYear event: %w", err)
				}
			}
		}
	}

	logMessage("Events table successfully exported to SQLite database")
	return nil
}

// generateBiographies generates biographies for each ruler based on their periods and titles
func generateBiographies(allPeriods [][]string, dbName string) error {
	logMessage("Generating ruler biographies...")

	db, err := sql.Open("sqlite3", dbName)
	if err != nil {
		return fmt.Errorf("failed to open database: %w", err)
	}
	defer db.Close()

	// Get all rulers with their data
	rows, err := db.Query("SELECT rulerID, name, personal_name, epithet FROM rulers")
	if err != nil {
		return fmt.Errorf("failed to query rulers: %w", err)
	}
	defer rows.Close()

	var rulers []rulerInfo
	for rows.Next() {
		var ruler rulerInfo
		if err := rows.Scan(&ruler.rulerID, &ruler.name, &ruler.personalName, &ruler.epithet); err != nil {
			return fmt.Errorf("failed to scan ruler: %w", err)
		}
		rulers = append(rulers, ruler)
	}

	// Organize periods by ruler
	rulerPeriods := make(map[int][]periodInfo)
	for i, row := range allPeriods {
		if i == 0 {
			// Skip header row
			continue
		}

		// Ensure row has enough columns
		for len(row) < 4 {
			row = append(row, "")
		}

		rulerIDStr := strings.TrimSpace(getValueOrDefault(row, 1, ""))
		if rulerIDStr == "" {
			continue
		}

		rulerID, err := strconv.Atoi(rulerIDStr)
		if err != nil {
			continue
		}

		period := periodInfo{
			title:  getValueOrDefault(row, 0, ""),
			period: getValueOrDefault(row, 2, ""),
			notes:  getValueOrDefault(row, 3, ""),
		}

		rulerPeriods[rulerID] = append(rulerPeriods[rulerID], period)
	}

	// Generate biography for each ruler
	biographiesUpdated := 0
	stmt, err := db.Prepare("UPDATE rulers SET biography = ? WHERE rulerID = ?")
	if err != nil {
		return fmt.Errorf("failed to prepare biography update statement: %w", err)
	}
	defer stmt.Close()

	for _, ruler := range rulers {
		periods, exists := rulerPeriods[ruler.rulerID]
		if !exists {
			continue
		}

		// Build the biography string
		var biographyParts []string

		// Start with personal name only (name will be handled by the Go application)
		if ruler.personalName != "" && strings.TrimSpace(ruler.personalName) != "" {
			biographyParts = append(biographyParts, strings.TrimSpace(ruler.personalName))
		}

		// Group periods by title for better formatting
		titleGroups := make(map[string][]periodInfo)
		for _, period := range periods {
			titleGroups[period.title] = append(titleGroups[period.title], period)
		}

		// Format each title group
		var titleParts []string
		for title, titlePeriods := range titleGroups {
			if len(titlePeriods) == 1 {
				// Single period
				periodStr := titlePeriods[0].period
				if titlePeriods[0].notes != "" && strings.TrimSpace(titlePeriods[0].notes) != "" {
					periodStr += ", " + strings.TrimSpace(titlePeriods[0].notes)
				}
				titleParts = append(titleParts, fmt.Sprintf("%s (%s)", title, periodStr))
			} else {
				// Multiple periods - include notes for each
				var periodStrs []string
				for _, period := range titlePeriods {
					periodStr := period.period
					if period.notes != "" && strings.TrimSpace(period.notes) != "" {
						periodStr += ", " + strings.TrimSpace(period.notes)
					}
					periodStrs = append(periodStrs, periodStr)
				}
				titleParts = append(titleParts, fmt.Sprintf("%s (%s)", title, strings.Join(periodStrs, "; ")))
			}
		}

		// Combine all parts
		if len(titleParts) > 0 {
			biographyParts = append(biographyParts, strings.Join(titleParts, "; "))
		}

		biography := strings.Join(biographyParts, ", ")

		// Update the database
		_, err = stmt.Exec(biography, ruler.rulerID)
		if err != nil {
			return fmt.Errorf("failed to update biography: %w", err)
		}
		biographiesUpdated++
	}

	logMessage("Generated biographies for %d rulers", biographiesUpdated)
	return nil
}

// periodData represents a single period record
type periodData struct {
	title      string
	rulerID    int
	period     string
	startYear  int
	endYear    int
	notes      string
	progrTitle int
}

// createTables creates the necessary database tables
func createTables(db *sql.DB) error {
	tables := []string{
		"DROP TABLE IF EXISTS titles",
		"DROP TABLE IF EXISTS years",
		"DROP TABLE IF EXISTS byPeriod",
		"DROP TABLE IF EXISTS byYear",
		`CREATE TABLE IF NOT EXISTS titles (
			titleID INTEGER PRIMARY KEY AUTOINCREMENT,
			title TEXT UNIQUE,
			maxCount INTEGER,
			titlePlural TEXT
		)`,
		`CREATE TABLE IF NOT EXISTS years (
			yearID INTEGER PRIMARY KEY AUTOINCREMENT,
			year INTEGER UNIQUE
		)`,
		`CREATE TABLE IF NOT EXISTS byPeriod (
			periodID INTEGER PRIMARY KEY AUTOINCREMENT,
			rulerID INTEGER,
			titleID INTEGER,
			progrTitle INTEGER,
			period TEXT,
			startYear INTEGER,
			endYear INTEGER,
			notes TEXT,
			FOREIGN KEY (rulerID) REFERENCES rulers (rulerID),
			FOREIGN KEY (titleID) REFERENCES titles (titleID)
		)`,
		`CREATE TABLE IF NOT EXISTS byYear (
			yearID INTEGER,
			periodID INTEGER,
			FOREIGN KEY (yearID) REFERENCES years (yearID),
			FOREIGN KEY (periodID) REFERENCES byPeriod (periodID),
			PRIMARY KEY (yearID, periodID)
		)`,
	}

	for _, sql := range tables {
		_, err := db.Exec(sql)
		if err != nil {
			return fmt.Errorf("failed to execute SQL: %s, error: %w", sql, err)
		}
	}

	return nil
}

// getValueOrDefault returns the value at index or default if index is out of bounds
func getValueOrDefault(row []string, index int, defaultValue string) string {
	if index < len(row) {
		return row[index]
	}
	return defaultValue
}

// batchInsertTitles inserts titles and returns mappings
func batchInsertTitles(db *sql.DB, titles map[string]bool) (map[string]int, error) {
	stmt, err := db.Prepare("INSERT OR IGNORE INTO titles (title) VALUES (?)")
	if err != nil {
		return nil, err
	}
	defer stmt.Close()

	for title := range titles {
		_, err = stmt.Exec(title)
		if err != nil {
			return nil, err
		}
	}

	// Get all titleIDs
	rows, err := db.Query("SELECT title, titleID FROM titles")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	titleMappings := make(map[string]int)
	for rows.Next() {
		var title string
		var titleID int
		if err := rows.Scan(&title, &titleID); err != nil {
			return nil, err
		}
		titleMappings[title] = titleID
	}

	return titleMappings, nil
}

// batchInsertYears inserts years and returns mappings
func batchInsertYears(db *sql.DB, allYears map[int]bool) (map[int]int, error) {
	stmt, err := db.Prepare("INSERT OR IGNORE INTO years (year) VALUES (?)")
	if err != nil {
		return nil, err
	}
	defer stmt.Close()

	for year := range allYears {
		_, err = stmt.Exec(year)
		if err != nil {
			return nil, err
		}
	}

	// Get all yearIDs
	rows, err := db.Query("SELECT year, yearID FROM years")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	yearMappings := make(map[int]int)
	for rows.Next() {
		var year, yearID int
		if err := rows.Scan(&year, &yearID); err != nil {
			return nil, err
		}
		yearMappings[year] = yearID
	}

	return yearMappings, nil
}

// batchInsertPeriods inserts period data
func batchInsertPeriods(db *sql.DB, periodsData []periodData, titleMappings map[string]int) error {
	stmt, err := db.Prepare(`
		INSERT INTO byPeriod (rulerID, titleID, progrTitle, period, startYear, endYear, notes)
		VALUES (?, ?, ?, ?, ?, ?, ?)
	`)
	if err != nil {
		return err
	}
	defer stmt.Close()

	for _, period := range periodsData {
		_, err = stmt.Exec(
			period.rulerID,
			titleMappings[period.title],
			period.progrTitle,
			period.period,
			period.startYear,
			period.endYear,
			period.notes,
		)
		if err != nil {
			return err
		}
	}

	return nil
}

// insertByYearData inserts byYear junction data
func insertByYearData(db *sql.DB, yearMappings map[int]int) error {
	// Get all period ranges
	rows, err := db.Query("SELECT periodID, startYear, endYear FROM byPeriod")
	if err != nil {
		return err
	}
	defer rows.Close()

	var periodRanges []struct {
		periodID  int
		startYear int
		endYear   int
	}

	for rows.Next() {
		var periodID, startYear, endYear int
		if err := rows.Scan(&periodID, &startYear, &endYear); err != nil {
			return err
		}
		periodRanges = append(periodRanges, struct {
			periodID  int
			startYear int
			endYear   int
		}{periodID, startYear, endYear})
	}

	// Insert byYear data
	stmt, err := db.Prepare("INSERT OR IGNORE INTO byYear (yearID, periodID) VALUES (?, ?)")
	if err != nil {
		return err
	}
	defer stmt.Close()

	for _, period := range periodRanges {
		for year := period.startYear; year <= period.endYear; year++ {
			if yearID, exists := yearMappings[year]; exists {
				_, err = stmt.Exec(yearID, period.periodID)
				if err != nil {
					return err
				}
			}
		}
	}

	return nil
}

// updateTitleMaxCounts updates maxCount for titles
func updateTitleMaxCounts(db *sql.DB, titleCheck map[string]int) error {
	stmt, err := db.Prepare("UPDATE titles SET maxCount = ? WHERE title = ?")
	if err != nil {
		return err
	}
	defer stmt.Close()

	for title, count := range titleCheck {
		_, err = stmt.Exec(count, title)
		if err != nil {
			return err
		}
	}

	return nil
}

// updateTitlePlurals updates plural forms for titles
func updateTitlePlurals(db *sql.DB) error {
	plurals := map[string]string{
		"Pope":                              "Popes",
		"English Monarch":                   "English Monarchs",
		"US president":                      "US presidents",
		"British Prime Minister":            "British Prime Ministers",
		"French Monarch":                    "French Monarchs",
		"King of the West Franks":           "Kings of the West Franks",
		"King of the East Franks":           "Kings of the East Franks",
		"King of the Franks":                "Kings of the Franks",
		"King of France":                    "Kings of France",
		"French Government":                 "French Governments",
		"French Emperor":                    "French Emperors",
		"French President":                  "French Presidents",
		"Byzantine Emperor":                 "Byzantine Emperors",
		"Emperor of China":                  "Emperors of China",
		"Holy Roman Emperor":                "Holy Roman Emperors",
		"Emperor of the Carolingian Empire": "Emperors of the Carolingian Empire",
		"Roman Emperor":                     "Roman Emperors",
		"Roman Emperor (East)":              "Roman Emperors (East)",
		"Roman Emperor (West)":              "Roman Emperors (West)",
		"Russian Emperor":                   "Russian Emperors",
		"Prince of Moscow":                  "Princes of Moscow",
		"Tsar of Russia":                    "Tsars of Russia",
		"Chairman of the Communist Party of the Soviet Union": "Chairmen of the Communist Party of the Soviet Union",
		"Russian President":    "Russian Presidents",
		"Antipope":             "Antipopes",
		"Scottish Monarch":     "Scottish Monarchs",
		"Neapolitan ruler":     "Neapolitan rulers",
		"Spanish Monarch":      "Spanish Monarchs",
		"King of the Lombards": "Kings of the Lombards",
		"Emperor of Austria":   "Emperors of Austria",
		"Roman Consul":         "Roman Consuls",
		"Decemvir":             "Decemviri",
		"Dictator":             "Dictators",
		"King of Italy":        "Kings of Italy",
		"Consular Tribune":     "Consular Tribunes",
		"King of Rome":         "Kings of Rome",
	}

	stmt, err := db.Prepare("UPDATE titles SET titlePlural = ? WHERE title = ?")
	if err != nil {
		return err
	}
	defer stmt.Close()

	for title, plural := range plurals {
		_, err = stmt.Exec(plural, title)
		if err != nil {
			return err
		}
	}

	return nil
}

// eventData represents a single event record
type eventData struct {
	eventName  string
	startYear  int
	endYear    int
	notes      string
	wikipedia  string
	startMonth *int // nil → NULL (no exact date on the sheet)
	startDay   *int
}

// parseOptionalInt returns a pointer to the parsed value, or nil for
// blanks/non-numbers, so empty sheet cells become SQL NULLs.
func parseOptionalInt(s string) *int {
	v, err := strconv.Atoi(strings.TrimSpace(s))
	if err != nil {
		return nil
	}
	return &v
}

// rulerInfo represents ruler information
type rulerInfo struct {
	rulerID      int
	name         string
	personalName string
	epithet      string
}

// periodInfo represents period information for biography generation
type periodInfo struct {
	title  string
	period string
	notes  string
}

// getYearMappings gets year to yearID mappings for the given years
func getYearMappings(db *sql.DB, years map[int]bool) (map[int]int, error) {
	if len(years) == 0 {
		return make(map[int]int), nil
	}

	// Build query with placeholders
	var placeholders []string
	var args []interface{}
	for year := range years {
		placeholders = append(placeholders, "?")
		args = append(args, year)
	}

	query := fmt.Sprintf("SELECT year, yearID FROM years WHERE year IN (%s)", strings.Join(placeholders, ","))
	rows, err := db.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	yearMappings := make(map[int]int)
	for rows.Next() {
		var year, yearID int
		if err := rows.Scan(&year, &yearID); err != nil {
			return nil, err
		}
		yearMappings[year] = yearID
	}

	return yearMappings, nil
}

// addEventIDColumn adds the eventID column to byYear table if it doesn't exist
func addEventIDColumn(db *sql.DB) error {
	// Check if the column exists
	rows, err := db.Query("PRAGMA table_info(byYear)")
	if err != nil {
		return err
	}
	defer rows.Close()

	columnExists := false
	for rows.Next() {
		var cid int
		var name, dataType string
		var notNull, pk int
		var defaultValue interface{}
		if err := rows.Scan(&cid, &name, &dataType, &notNull, &defaultValue, &pk); err != nil {
			return err
		}
		if name == "eventID" {
			columnExists = true
			break
		}
	}

	if !columnExists {
		_, err = db.Exec("ALTER TABLE byYear ADD COLUMN eventID INTEGER")
		if err != nil {
			return err
		}
		_, err = db.Exec("CREATE INDEX IF NOT EXISTS idx_byYear_eventID ON byYear(eventID)")
		if err != nil {
			return err
		}
	}

	return nil
}
