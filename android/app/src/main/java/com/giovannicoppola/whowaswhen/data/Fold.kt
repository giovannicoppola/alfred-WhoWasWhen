package com.giovannicoppola.whowaswhen.data

import java.text.Normalizer

/**
 * Accent- and case-insensitive folding used for search.
 *
 * Mirrors `foldForSearch` in the iOS app (and the Go workflow's
 * `pkg/search_fold.go`): lowercase, normalize the German sharp S, then strip
 * combining marks (diacritics) so e.g. "Jérôme" matches "jerome".
 */
fun foldForSearch(input: String): String {
    var s = input.trim().lowercase()
    s = s.replace("ß", "ss").replace("ẞ", "ss")
    // Decompose then drop combining marks (Unicode category Mn).
    val decomposed = Normalizer.normalize(s, Normalizer.Form.NFD)
    return decomposed.replace(Regex("\\p{Mn}+"), "")
}

/** Normalizes raw search-box text before it is split into terms. */
fun normalizeSearchInput(input: String): String = foldForSearch(input)
