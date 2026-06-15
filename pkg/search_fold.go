package main

import (
	"database/sql"
	"fmt"
	"strings"
	"unicode"

	"github.com/mattn/go-sqlite3"
	"golang.org/x/text/runes"
	"golang.org/x/text/transform"
	"golang.org/x/text/unicode/norm"
)

func init() {
	sql.Register("sqlite3_fold", &sqlite3.SQLiteDriver{
		ConnectHook: func(conn *sqlite3.SQLiteConn) error {
			return conn.RegisterFunc("fold", sqliteFold, true)
		},
	})
}

func sqliteFold(arg any) any {
	if arg == nil {
		return ""
	}
	switch v := arg.(type) {
	case string:
		return foldForSearch(v)
	case []byte:
		return foldForSearch(string(v))
	default:
		return foldForSearch(fmt.Sprint(v))
	}
}

func foldForSearch(s string) string {
	s = strings.TrimSpace(strings.ToLower(s))
	s = strings.ReplaceAll(s, "ß", "ss")
	s = strings.ReplaceAll(s, "ẞ", "ss")

	transformer := transform.Chain(norm.NFD, runes.Remove(runes.In(unicode.Mn)), norm.NFC)
	out, _, err := transform.String(transformer, s)
	if err != nil {
		return s
	}
	return out
}

func normalizeSearchInput(input string) string {
	return foldForSearch(strings.TrimSpace(strings.ToLower(input)))
}

func foldLikeSQL(column, term string) string {
	folded := foldForSearch(term)
	return fmt.Sprintf("fold(%s) LIKE '%%%s%%'", column, folded)
}

func buildFoldedTextSQL(columns []string, terms []string, joinTermsWith string) string {
	if len(terms) == 0 {
		return "1=1"
	}

	termConditions := make([]string, 0, len(terms))
	for _, term := range terms {
		parts := make([]string, 0, len(columns))
		for _, column := range columns {
			parts = append(parts, foldLikeSQL(column, term))
		}
		termConditions = append(termConditions, "("+strings.Join(parts, " OR ")+")")
	}
	return strings.Join(termConditions, joinTermsWith)
}

func openWhoWasWhenDB(path string) (*sql.DB, error) {
	return sql.Open("sqlite3_fold", path)
}
