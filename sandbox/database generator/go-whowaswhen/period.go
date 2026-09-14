package main

import (
	"fmt"
	"strconv"
	"strings"
)

// parsePeriod parses a period string into start and end years
func parsePeriod(years string) (int, int, error) {
	years = strings.TrimSpace(years)

	// Handle en dashes first (easier case)
	if strings.Contains(years, "–") {
		parts := strings.Split(years, "–")
		if len(parts) != 2 {
			return 0, 0, fmt.Errorf("invalid period format with en dash: %s", years)
		}
		return parseYearRange(strings.TrimSpace(parts[0]), strings.TrimSpace(parts[1]))
	}

	// Handle regular hyphens - need to distinguish between negative numbers and ranges
	if strings.Contains(years, "-") {
		// If it starts with a minus, it could be:
		// 1. A single negative year like "-776"
		// 2. A range starting with negative like "-27-180"
		if strings.HasPrefix(years, "-") {
			// Look for a second dash
			secondDashPos := strings.Index(years[1:], "-")
			if secondDashPos > 0 {
				// It's a range: "-27-180"
				startYear := years[:secondDashPos+1]
				endYear := years[secondDashPos+2:]
				return parseYearRange(startYear, endYear)
			} else {
				// It's a single negative year: "-776"
				year, err := parseYear(years)
				if err != nil {
					return 0, 0, err
				}
				return year, year, nil
			}
		} else {
			// Regular positive range like "1509-1547"
			parts := strings.Split(years, "-")
			if len(parts) != 2 {
				return 0, 0, fmt.Errorf("invalid period format with hyphen: %s", years)
			}
			return parseYearRange(strings.TrimSpace(parts[0]), strings.TrimSpace(parts[1]))
		}
	}

	// Single year (no separator)
	year, err := parseYear(years)
	if err != nil {
		return 0, 0, err
	}
	return year, year, nil
}

// parseYearRange parses start and end year strings
func parseYearRange(startYearStr, endYearStr string) (int, int, error) {
	startYear, err := parseYear(startYearStr)
	if err != nil {
		return 0, 0, fmt.Errorf("invalid start year: %w", err)
	}

	endYear, err := parseYear(endYearStr)
	if err != nil {
		return 0, 0, fmt.Errorf("invalid end year: %w", err)
	}

	// Handle short form end year like '95' in '1981-95'
	if len(endYearStr) <= 2 && startYear > 0 && endYear < 100 {
		startYearStr := strconv.Itoa(startYear)
		if len(startYearStr) > len(endYearStr) {
			prefix := startYearStr[:len(startYearStr)-len(endYearStr)]
			fullEndYear, err := strconv.Atoi(prefix + endYearStr)
			if err == nil {
				endYear = fullEndYear
			}
		}
	}

	return startYear, endYear, nil
}

// parseYear parses a single year string (handles BC/AD)
func parseYear(yearStr string) (int, error) {
	yearStr = strings.TrimSpace(yearStr)

	if strings.Contains(yearStr, "BC") {
		yearStr = strings.Replace(yearStr, "BC", "", -1)
		yearStr = strings.TrimSpace(yearStr)
		year, err := strconv.Atoi(yearStr)
		if err != nil {
			return 0, fmt.Errorf("invalid BC year: %s", yearStr)
		}
		return -year, nil
	}

	if strings.Contains(yearStr, "AD") {
		yearStr = strings.Replace(yearStr, "AD", "", -1)
		yearStr = strings.TrimSpace(yearStr)
		year, err := strconv.Atoi(yearStr)
		if err != nil {
			return 0, fmt.Errorf("invalid AD year: %s", yearStr)
		}
		return year, nil
	}

	year, err := strconv.Atoi(yearStr)
	if err != nil {
		return 0, fmt.Errorf("invalid year: %s", yearStr)
	}

	return year, nil
}
