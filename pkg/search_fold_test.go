package main

import "testing"

func TestFoldForSearch(t *testing.T) {
	cases := map[string]string{
		"Lützen":     "lutzen",
		"Nördlingen": "nordlingen",
		"José":       "jose",
		"François":   "francois",
		"Straße":     "strasse",
		"  Mixed  ":  "mixed",
	}
	for input, want := range cases {
		if got := foldForSearch(input); got != want {
			t.Fatalf("foldForSearch(%q) = %q, want %q", input, got, want)
		}
	}
}
