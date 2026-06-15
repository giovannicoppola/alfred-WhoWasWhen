import Foundation

/// Accent- and case-insensitive folding used for search.
///
/// Mirrors `foldForSearch` in the Go workflow (`pkg/search_fold.go`):
/// lowercase, normalize the German sharp S, then strip combining marks
/// (diacritics) so e.g. "Jérôme" matches "jerome".
///
/// This is a free (non-capturing) function so it can be passed to SQLite as a
/// plain C function pointer when registering the `fold()` SQL function.
func foldForSearch(_ input: String) -> String {
    var s = input.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    s = s.replacingOccurrences(of: "ß", with: "ss")
    s = s.replacingOccurrences(of: "ẞ", with: "ss")
    return s.folding(options: .diacriticInsensitive,
                     locale: Locale(identifier: "en_US_POSIX"))
}

/// Normalizes raw search-box text before it is split into terms.
func normalizeSearchInput(_ input: String) -> String {
    foldForSearch(input)
}
