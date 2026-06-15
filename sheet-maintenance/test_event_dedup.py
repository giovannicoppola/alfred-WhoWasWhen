#!/usr/bin/env python3
"""Tests for event duplicate / similarity detection."""

import unittest

from sheets_common import (
    enrich_existing_event_row,
    event_duplicate_reason,
    event_name_core,
    fold_event_name,
    fold_for_search,
    should_merge_events,
)


class EventDedupTests(unittest.TestCase):
    def test_fold_for_search(self):
        self.assertEqual(fold_for_search("Lützen"), "lutzen")
        self.assertEqual(fold_for_search("  Nördlingen  "), "nordlingen")
        self.assertEqual(fold_for_search("Straße"), "strasse")

    def test_accent_insensitive_duplicate(self):
        existing = enrich_existing_event_row(
            "Battle of Lützen (November 16)",
            {"progr": 997, "row_idx": 914, "name": "Battle of Lützen (November 16)"},
        )
        self.assertEqual(
            event_duplicate_reason("Battle of Lutzen (November 16)", existing),
            "accent-insensitive name match",
        )

    def test_core_name_duplicate_without_date(self):
        existing = enrich_existing_event_row(
            "Battle of Lützen (November 16)",
            {"progr": 997, "row_idx": 914, "name": "Battle of Lützen (November 16)"},
        )
        self.assertEqual(
            event_duplicate_reason("Battle of Lützen", existing),
            "same core name (ignoring dates and accents)",
        )

    def test_should_merge_similar_same_year(self):
        a = enrich_existing_event_row(
            "Fall of Western Roman Empire",
            {"progr": 86, "row_idx": 1, "name": "Fall of Western Roman Empire", "sorting_year": "476"},
        )
        b = enrich_existing_event_row(
            "Fall of the Western Roman Empire",
            {"progr": 89, "row_idx": 2, "name": "Fall of the Western Roman Empire", "sorting_year": "476"},
        )
        ok, reason = should_merge_events(a, b)
        self.assertTrue(ok)
        self.assertIn("similar", reason)

    def test_no_false_merge_for_different_battles(self):
        a = enrich_existing_event_row(
            "Battle of Rocroi (May 19)",
            {"progr": 1000, "row_idx": 917, "name": "Battle of Rocroi (May 19)", "sorting_year": "1643"},
        )
        b = enrich_existing_event_row(
            "Battle of Lützen (November 16)",
            {"progr": 997, "row_idx": 914, "name": "Battle of Lützen (November 16)", "sorting_year": "1632"},
        )
        self.assertFalse(should_merge_events(a, b)[0])


if __name__ == "__main__":
    unittest.main()
