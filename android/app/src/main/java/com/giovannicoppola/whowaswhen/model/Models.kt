package com.giovannicoppola.whowaswhen.model

import java.text.NumberFormat
import java.util.Locale
import java.util.UUID

enum class ResultKind { RULER, EVENT }

/**
 * A single row of search output, covering both rulers and events.
 * Mirrors the iOS `SearchResult` (and the fields an Alfred item carries),
 * so the same actions are possible.
 */
data class SearchResult(
    val kind: ResultKind,
    var title: String,
    var subtitle: String,
    /** Wikipedia (or fallback) link opened on tap / "Open Wikipedia". */
    val wikipediaUrl: String? = null,
    /** Years used by the "travel to start/end year" actions. */
    val startYear: Int,
    val endYear: Int,
    /** For rulers: the title and its plural, used by "Show all «title»". */
    val titleName: String? = null,
    val titlePlural: String? = null,
    val rulerID: Int? = null,
    val progrTitle: Int? = null,
    /** For rulers: the personal name or house/dynasty, shown as its own line. */
    val personalName: String? = null,
    /** For events: the stable database key (used by Favorites). */
    val eventID: Int? = null,
    /** For dated events: the calendar month/day of the start. */
    val startMonth: Int? = null,
    val startDay: Int? = null,
    /** For rulers: birth/death years where known (negative = BC). */
    val born: Int? = null,
    val died: Int? = null,
    /** Marks the focused ruler in a lineage list (the 🌟 in the workflow). */
    val isCurrent: Boolean = false,
    /** Asset name (bundled icon) or fallback resolved in the view. */
    val iconAsset: String? = null,
    /** Stable identity — every result is unique, matching the iOS UUID id. */
    val id: String = UUID.randomUUID().toString(),
) {
    /** Plain-text rendering for the "Copy" action. */
    val copyText: String get() = "$title: $subtitle"
}

/** Information about one reign period, used to build ruler subtitles. */
data class PeriodInfo(
    val period: String,
    val notes: String,
    val title: String,
    val startYear: Int,
    val endYear: Int,
    val progrTitle: Int,
)

/** Lower number = higher priority. Ported from the Go `getTitleRank`. */
object TitleRanking {
    fun rank(title: String): Int {
        val t = title.lowercase()
        if (t.contains("roman emperor")) return 1
        if (t.contains("byzantine emperor")) return 2
        if (t.contains("holy roman emperor")) return 3
        if (t.contains("king") || t.contains("queen")) return 10
        if (t.contains("emperor")) return 15
        if (t.contains("tsar") || t.contains("czar")) return 20
        if (t.contains("president")) return 30
        if (t.contains("prime minister") || t.contains("premier")) return 35
        if (t.contains("chancellor")) return 40
        if (t.contains("duke") || t.contains("duchess")) return 50
        if (t.contains("pope")) return 55
        if (t.contains("patriarch")) return 60
        if (t.contains("consul")) return 100
        if (t.contains("tribune")) return 110
        if (t.contains("dictator")) return 120
        return 1000
    }
}

/**
 * Builds the multi-period ruler subtitle, e.g.
 * "Personal Name, Title (1500-1510; 1512, note); Other Title (1520)".
 * Ported from the Go/iOS `formatSubtitle`.
 */
fun formatRulerSubtitle(periods: List<PeriodInfo>, personalName: String?): String {
    // Group periods by title, preserving encounter order within a group.
    val groups = LinkedHashMap<String, MutableList<PeriodInfo>>()
    for (p in periods) groups.getOrPut(p.title) { mutableListOf() }.add(p)

    val sortedGroups = groups.entries.sortedBy { TitleRanking.rank(it.key) }

    val titleParts = ArrayList<String>()
    for ((title, groupPeriods) in sortedGroups) {
        val periodParts = ArrayList<String>()
        for (p in groupPeriods) {
            var periodStr = if (p.startYear == p.endYear) {
                formatYear(p.startYear)
            } else {
                "${formatYear(p.startYear)}-${formatYear(p.endYear)}"
            }
            if (p.notes.isNotEmpty() && p.notes != ",") {
                periodStr += ", ${p.notes}"
            }
            periodParts.add(periodStr)
        }
        titleParts.add("$title (${periodParts.joinToString("; ")})")
    }

    val titlesString = titleParts.joinToString("; ")
    return if (!personalName.isNullOrEmpty()) "$personalName, $titlesString" else titlesString
}

/** Plural title with the same fallback as the Go `getTitlePlural`. */
fun titlePluralOrDefault(plural: String?, title: String): String {
    if (!plural.isNullOrEmpty()) return plural
    return title + "s"
}

/** Formats a year with BC/AD, matching the Go `formatYear`. */
fun formatYear(year: Int): String = if (year < 0) "${-year} BC" else "$year"

/** Adds thousands separators, matching the Go `formatNumber`. */
fun formatNumber(n: Int): String =
    NumberFormat.getIntegerInstance(Locale.US).format(n.toLong())

/** A quiz-eligible title, doubling as a quiz category. */
data class TitleInfo(
    val titleID: Int,
    val title: String,
    val titlePlural: String?,
    val maxCount: Int,
)

/** One reign of one holder of a title (quiz distractors + timelines). */
data class HolderRow(
    val rulerID: Int,
    val name: String,
    val period: String,
    val startYear: Int,
    val endYear: Int,
    val progrTitle: Int,
)

/** An event stripped to what a quiz question needs. */
data class QuizEventRow(
    val eventID: Int,
    val name: String,
    val startYear: Int,
    val endYear: Int,
)

/**
 * A key work linked to its creator (the `works` table) — the "Who wrote
 * «work»?" quiz material.
 */
data class WorkRow(
    val title: String,
    val year: Int,
    val category: String,
    val creatorRulerID: Int,
    val creatorName: String,
)
