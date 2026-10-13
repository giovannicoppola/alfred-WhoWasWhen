package com.giovannicoppola.whowaswhen.data

import com.giovannicoppola.whowaswhen.model.formatYear

/**
 * Parses the search box into the same three modes as the Alfred workflow:
 * a year/wildcard/range term, free-text terms, or a mix of both.
 */
object QueryParser {

    /** A parsed query, ready to hand to the database layer. */
    data class Parsed(val yearTerm: String?, val textTerms: List<String>)

    /**
     * Matches a year, a BC year, a wildcard year, or a range. Mirrors the Go
     * `isNumberLike` regex: `^-?\d*\**$|^-?\d*\**--?\d*\**$`
     */
    private val numberLike = Regex("""^-?\d*\**$|^-?\d*\**--?\d*\**$""")

    fun isNumberLike(term: String): Boolean {
        if (term.isEmpty()) return false
        // A bare "-" or "*" alone is not a useful year term.
        if (term == "-" || term.all { it == '*' }) return false
        return numberLike.matches(term)
    }

    fun parse(raw: String): Parsed {
        val normalized = normalizeSearchInput(raw)
        val terms = normalized.split(" ").filter { it.isNotEmpty() }

        var yearTerm: String? = null
        val textTerms = ArrayList<String>()
        for (term in terms) {
            if (yearTerm == null && isNumberLike(term)) {
                yearTerm = term
            } else {
                textTerms.add(term)
            }
        }
        return Parsed(yearTerm, textTerms)
    }

    /** Resolved bounds for a year term, used to build the SQL `WHERE` clause. */
    sealed interface YearClause {
        /** `y.year BETWEEN lower AND upper` */
        data class Range(val lower: Int, val upper: Int) : YearClause
        /** `CAST(y.year AS TEXT) LIKE 'prefix____'` for wildcard searches. */
        data class Like(val pattern: String) : YearClause
    }

    /** Translates a year term into a SQL clause, mirroring the Go `byYear` logic. */
    fun yearClause(term: String): YearClause {
        val asteriskCount = term.reversed().takeWhile { it == '*' }.count()

        // Range: a single internal dash, not a leading minus (e.g. "1500-1600").
        if (asteriskCount == 0) {
            parseRange(term)?.let { return YearClause.Range(it.first, it.second) }
        }

        // Wildcard or plain year -> LIKE on the textual year.
        val prefix = term.dropLast(asteriskCount)
        val pattern = prefix + "_".repeat(asteriskCount)
        return YearClause.Like(pattern)
    }

    /** Parses "1500-1600" or "-100--50" style ranges. Returns null for single years. */
    private fun parseRange(term: String): Pair<Int, Int>? {
        // Single internal dash, no leading minus: "1500-1600"
        if (!term.startsWith("-") && term.count { it == '-' } == 1) {
            val parts = term.split("-", limit = 2)
            if (parts.size == 2) {
                val a = parts[0].toIntOrNull()
                val b = parts[1].toIntOrNull()
                if (a != null && b != null) return Pair(minOf(a, b), maxOf(a, b))
            }
        }
        // Ranges that include a negative bound: "-100--50", "-44-100"
        if (term.count { it == '-' } > 1) {
            matchSignedRange(term)?.let { return Pair(minOf(it.first, it.second), maxOf(it.first, it.second)) }
        }
        return null
    }

    private val signedRange = Regex("""^(-?\d+)-(-?\d+)$""")

    private fun matchSignedRange(term: String): Pair<Int, Int>? {
        val m = signedRange.matchEntire(term) ?: return null
        val a = m.groupValues[1].toIntOrNull() ?: return null
        val b = m.groupValues[2].toIntOrNull() ?: return null
        return Pair(a, b)
    }

    /** Whether a year term denotes a span (range or wildcard) rather than a single year. */
    fun isSpan(term: String): Boolean {
        if (term.contains("*")) return true
        return parseRange(term) != null
    }

    /**
     * The year label to show once at the top of year-search results
     * (e.g. "1789", "44 BC", "177*", "1500-1600"), or null for a text-only query.
     */
    fun displayYear(query: String): String? {
        val term = parse(query).yearTerm ?: return null
        if (term.contains("*")) return term
        parseRange(term)?.let { return "${formatYear(it.first)}–${formatYear(it.second)}" }
        term.toIntOrNull()?.let { return formatYear(it) }
        return term
    }
}
