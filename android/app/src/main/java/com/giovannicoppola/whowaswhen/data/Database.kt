package com.giovannicoppola.whowaswhen.data

import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.net.Uri
import com.giovannicoppola.whowaswhen.model.HolderRow
import com.giovannicoppola.whowaswhen.model.PeriodInfo
import com.giovannicoppola.whowaswhen.model.QuizEventRow
import com.giovannicoppola.whowaswhen.model.ResultKind
import com.giovannicoppola.whowaswhen.model.SearchResult
import com.giovannicoppola.whowaswhen.model.TitleInfo
import com.giovannicoppola.whowaswhen.model.TitleRanking
import com.giovannicoppola.whowaswhen.model.WorkRow
import com.giovannicoppola.whowaswhen.model.formatNumber
import com.giovannicoppola.whowaswhen.model.formatRulerSubtitle
import com.giovannicoppola.whowaswhen.model.formatYear

/** How the search is filtered: everything, people only, or events only. */
enum class SearchScope(val label: String) {
    ALL("All"),
    RULERS("People"),
    EVENTS("Events"),
}

/**
 * Read-only access to the WhoWasWhen SQLite database.
 *
 * Ports the query logic from the iOS app / Alfred workflow: search by year,
 * search rulers + events by text, and list a title's lineage. Text search uses
 * the precomputed `*_fold` columns (see [DatabaseProvider]) in place of the
 * iOS `fold()` SQL function.
 */
class Database(path: String) {

    private val db: SQLiteDatabase =
        SQLiteDatabase.openDatabase(path, null, SQLiteDatabase.OPEN_READONLY)

    private val hasEventDates: Boolean = columnExists("byEvents", "startMonth")
    private val hasLifespans: Boolean = columnExists("rulers", "born")

    fun close() = db.close()

    private fun columnExists(table: String, column: String): Boolean {
        db.rawQuery("PRAGMA table_info($table)", null).use { c ->
            val nameIdx = c.getColumnIndex("name")
            while (c.moveToNext()) if (c.getString(nameIdx) == column) return true
        }
        return false
    }

    private fun tableExists(name: String): Boolean {
        db.rawQuery(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", arrayOf(name)
        ).use { c -> return c.moveToNext() }
    }

    // MARK: - Top-level dispatch

    fun search(query: String, scope: SearchScope): List<SearchResult> {
        val parsed = QueryParser.parse(query)
        if (parsed.yearTerm == null && parsed.textTerms.isEmpty()) return emptyList()

        val includeRulers = scope != SearchScope.EVENTS
        val includeEvents = scope != SearchScope.RULERS

        return if (parsed.yearTerm != null) {
            searchByYear(parsed.yearTerm, parsed.textTerms, includeRulers, includeEvents)
        } else {
            searchByText(parsed.textTerms, includeRulers, includeEvents)
        }
    }

    fun searchByYear(
        yearTerm: String, textTerms: List<String>,
        includeRulers: Boolean, includeEvents: Boolean,
    ): List<SearchResult> {
        val out = ArrayList<SearchResult>()
        if (includeRulers) out += rulersByYear(yearTerm, textTerms)
        if (includeEvents) out += eventsByYear(yearTerm, textTerms)
        return out
    }

    fun searchByText(
        terms: List<String>, includeRulers: Boolean, includeEvents: Boolean,
    ): List<SearchResult> {
        val out = ArrayList<SearchResult>()
        if (includeRulers) out += rulersByText(terms)
        if (includeEvents) out += eventsByText(terms)
        return out
    }

    // MARK: - Lineage

    fun lineage(title: String, focusRulerID: Int?, focusProg: Int?): List<SearchResult> {
        val sql = """
            SELECT ru.rulerID, ru.name, ru.personal_name, ru.epithet, ru.wikipedia,
                   ru.biography, per.progrTitle, per.period, per.startYear, per.endYear,
                   per.notes, t.title, t.maxCount, t.titlePlural${lifespanColumns("ru")}
            FROM rulers ru
            JOIN byPeriod per ON ru.rulerID = per.rulerID
            JOIN titles t ON per.titleID = t.titleID
            WHERE t.title = ?
            ORDER BY per.progrTitle ASC;
        """.trimIndent()

        val rows = ArrayList<SearchResult>()
        db.rawQuery(sql, arrayOf(title)).use { c ->
            while (c.moveToNext()) {
                val rulerID = c.intAt(0)
                val name = c.str(1)
                val personal = c.strOpt(2)
                val wiki = c.strOpt(4)
                val biography = c.strOpt(5)
                val prog = c.intAt(6)
                val period = c.str(7)
                val startYear = c.intAt(8)
                val endYear = c.intAt(9)
                val notes = c.strOpt(10) ?: ""
                val titleName = c.str(11)
                val maxCount = c.intAt(12)
                val titlePlural = c.strOpt(13)

                val isCurrent = focusRulerID == rulerID && focusProg == prog
                val star = if (focusRulerID == rulerID) " 🌟" else ""
                val displayTitle = "$name ($period)$star"

                val counter = "${formatNumber(prog)}/${formatNumber(maxCount)}"
                val subtitle = if (!biography.isNullOrEmpty()) {
                    "$counter $biography"
                } else {
                    val notePart = if (notes.isEmpty() || notes == ",") "" else notes
                    "$counter $titleName $notePart"
                }

                rows += SearchResult(
                    kind = ResultKind.RULER, title = displayTitle, subtitle = subtitle,
                    wikipediaUrl = wikipediaLink(wiki, name),
                    startYear = startYear, endYear = endYear,
                    titleName = titleName, titlePlural = titlePlural,
                    rulerID = rulerID, progrTitle = prog,
                    personalName = personal,
                    born = if (hasLifespans) c.intOpt(14) else null,
                    died = if (hasLifespans) c.intOpt(15) else null,
                    isCurrent = isCurrent,
                    iconAsset = titleName,
                )
            }
        }
        return rows
    }

    // MARK: - Ruler queries

    private fun rulersByYear(yearTerm: String, textTerms: List<String>): List<SearchResult> {
        val yc = QueryParser.yearClause(yearTerm)
        val (yearSQL, yearParams) = yearClauseSQL(yc, "y.year")
        val (textSQL, textParams) = foldedTextSQL(listOf("r.name_fold", "t.title_fold"), textTerms)

        // Single-year search rows can say how old the ruler was then.
        var searchedYear: Int? = null
        when (yc) {
            is QueryParser.YearClause.Range -> if (yc.lower == yc.upper) searchedYear = yc.lower
            is QueryParser.YearClause.Like -> if (!yc.pattern.contains("_")) searchedYear = yc.pattern.toIntOrNull()
        }

        var sql = """
            SELECT r.rulerID, r.name, r.personal_name, r.epithet, r.wikipedia, r.notes,
                   per.progrTitle, per.period, per.startYear, per.endYear, per.notes,
                   t.title, t.maxCount, t.titlePlural, y.year${lifespanColumns("r")}
            FROM byYear rt
            JOIN byPeriod per ON rt.periodID = per.periodID
            JOIN rulers r ON per.rulerID = r.rulerID
            JOIN titles t ON per.titleID = t.titleID
            JOIN years y ON rt.yearID = y.yearID
            WHERE $yearSQL
        """.trimIndent()
        if (textTerms.isNotEmpty()) sql += " AND $textSQL"
        sql += " GROUP BY per.periodID ORDER BY y.year;"

        val rows = ArrayList<SearchResult>()
        db.rawQuery(sql, (yearParams + textParams).toTypedArray()).use { c ->
            while (c.moveToNext()) {
                val rulerID = c.intAt(0)
                val name = c.str(1)
                val personal = c.strOpt(2)
                val epithet = c.strOpt(3)
                val wiki = c.strOpt(4)
                val prog = c.intAt(6)
                val period = c.str(7)
                val startYear = c.intAt(8)
                val endYear = c.intAt(9)
                val notes = c.strOpt(10) ?: ""
                val titleName = c.str(11)
                val maxCount = c.intAt(12)
                val titlePlural = c.strOpt(13)

                val epithetString = if (!epithet.isNullOrEmpty()) " ($epithet)" else ""
                val displayTitle = "$name$epithetString ($period)"
                val counter = "${formatNumber(prog)}/${formatNumber(maxCount)}"
                var subtitle = "$titleName ($counter) $notes"

                val born = if (hasLifespans) c.intOpt(15) else null
                val died = if (hasLifespans) c.intOpt(16) else null
                if (searchedYear != null) {
                    val year = searchedYear!!
                    val suffix: String? = when {
                        born != null && born == year -> "born this year"
                        died != null && died == year -> "died this year"
                        born != null && year > born -> "age ${year - born}"
                        else -> null
                    }
                    if (suffix != null) subtitle = subtitle.trim() + " — $suffix"
                }

                rows += SearchResult(
                    kind = ResultKind.RULER, title = displayTitle, subtitle = subtitle,
                    wikipediaUrl = wikipediaLink(wiki, name),
                    startYear = startYear, endYear = endYear,
                    titleName = titleName, titlePlural = titlePlural,
                    rulerID = rulerID, progrTitle = prog,
                    personalName = personal,
                    born = born, died = died, iconAsset = titleName,
                )
            }
        }
        return rows
    }

    private fun rulersByText(terms: List<String>): List<SearchResult> {
        val (textSQL, textParams) = foldedTextSQL(
            listOf("ru.name_fold", "ru.personal_name_fold", "ru.epithet_fold", "ru.notes_fold", "t.title_fold"),
            terms,
        )
        val sql = """
            SELECT ru.rulerID, ru.name, ru.personal_name, ru.epithet, ru.wikipedia,
                   ru.biography, per.progrTitle, per.period, per.startYear, per.endYear,
                   per.notes, t.title, t.titlePlural${lifespanColumns("ru")}
            FROM rulers ru
            JOIN byPeriod per ON ru.rulerID = per.rulerID
            JOIN titles t ON per.titleID = t.titleID
            WHERE $textSQL
            ORDER BY ru.rulerID, per.startYear;
        """.trimIndent()
        db.rawQuery(sql, textParams.toTypedArray()).use { c -> return collectRulerRows(c) }
    }

    /** One data class for a ruler's non-period metadata during grouping. */
    private data class RulerMeta(
        val name: String, val personal: String?, val epithet: String?,
        val wiki: String?, val biography: String?, val titlePlural: String?,
        val titleName: String, val born: Int?, val died: Int?,
    )

    /**
     * Steps a rulers+periods statement (the 13-column SELECT used by
     * [rulersByText] and [rulerById]) into one row per ruler, grouping
     * multiple reign periods into a single subtitle.
     */
    private fun collectRulerRows(c: Cursor): List<SearchResult> {
        val order = ArrayList<Int>()
        val periodsByRuler = LinkedHashMap<Int, MutableList<PeriodInfo>>()
        val meta = HashMap<Int, RulerMeta>()

        while (c.moveToNext()) {
            val rulerID = c.intAt(0)
            if (!periodsByRuler.containsKey(rulerID)) order.add(rulerID)
            meta[rulerID] = RulerMeta(
                name = c.str(1), personal = c.strOpt(2), epithet = c.strOpt(3),
                wiki = c.strOpt(4), biography = c.strOpt(5), titlePlural = c.strOpt(12),
                titleName = c.str(11),
                born = if (hasLifespans) c.intOpt(13) else null,
                died = if (hasLifespans) c.intOpt(14) else null,
            )
            periodsByRuler.getOrPut(rulerID) { ArrayList() }.add(
                PeriodInfo(
                    period = c.str(7), notes = c.strOpt(10) ?: "",
                    title = c.str(11), startYear = c.intAt(8),
                    endYear = c.intAt(9), progrTitle = c.intAt(6),
                )
            )
        }

        val rows = ArrayList<SearchResult>()
        for (rulerID in order) {
            val m = meta[rulerID] ?: continue
            val periods = periodsByRuler[rulerID] ?: continue
            val epithetString = if (!m.epithet.isNullOrEmpty()) " (${m.epithet})" else ""
            val displayTitle = "${m.name}$epithetString"
            val subtitle = if (!m.biography.isNullOrEmpty()) {
                m.biography
            } else {
                formatRulerSubtitle(periods, personalName = null)
            }

            val earliest = periods.minOfOrNull { it.startYear } ?: 0
            val latest = periods.maxOfOrNull { it.endYear } ?: 0
            val topTitle = periods.minByOrNull { TitleRanking.rank(it.title) }?.title ?: m.titleName

            rows += SearchResult(
                kind = ResultKind.RULER, title = displayTitle, subtitle = subtitle,
                wikipediaUrl = wikipediaLink(m.wiki, m.name),
                startYear = earliest, endYear = latest,
                titleName = topTitle, titlePlural = m.titlePlural,
                rulerID = rulerID, progrTitle = periods.firstOrNull()?.progrTitle,
                personalName = m.personal,
                born = m.born, died = m.died,
                iconAsset = topTitle,
            )
        }
        return rows
    }

    private fun lifespanColumns(alias: String): String =
        if (hasLifespans) ", $alias.born, $alias.died" else ""

    // MARK: - Event queries

    private val eventColumns: String
        get() {
            var cols = "e.eventID, e.eventName, e.startYear, e.endYear, e.notes, e.wikipedia"
            if (hasEventDates) cols += ", e.startMonth, e.startDay"
            return cols
        }

    private fun eventsByYear(yearTerm: String, textTerms: List<String>): List<SearchResult> {
        val yc = QueryParser.yearClause(yearTerm)
        val (yearSQL, yearParams) = yearClauseSQL(yc, "y.year")
        val (textSQL, textParams) = foldedTextSQL(listOf("e.eventName_fold", "e.notes_fold"), textTerms)

        var sql = """
            SELECT $eventColumns
            FROM byYear rt
            JOIN byEvents e ON rt.eventID = e.eventID
            JOIN years y ON rt.yearID = y.yearID
            WHERE $yearSQL
        """.trimIndent()
        if (textTerms.isNotEmpty()) sql += " AND $textSQL"
        sql += " ORDER BY y.year;"

        val rows = ArrayList<SearchResult>()
        db.rawQuery(sql, (yearParams + textParams).toTypedArray()).use { c ->
            while (c.moveToNext()) {
                val name = c.str(1)
                val startYear = c.intAt(2)
                val endYear = c.intAt(3)
                val rangeStr = if (startYear != endYear)
                    " (${formatYear(startYear)}-${formatYear(endYear)})" else ""
                val row = eventRow(c).copy(title = "$name$rangeStr")
                rows += row
            }
        }
        return rows
    }

    private fun eventsByText(terms: List<String>): List<SearchResult> {
        val (textSQL, textParams) = foldedTextSQL(listOf("e.eventName_fold", "e.notes_fold"), terms)
        val sql = """
            SELECT $eventColumns
            FROM byEvents e
            WHERE $textSQL
            ORDER BY e.startYear;
        """.trimIndent()
        val rows = ArrayList<SearchResult>()
        db.rawQuery(sql, textParams.toTypedArray()).use { c ->
            while (c.moveToNext()) rows += eventRow(c)
        }
        return rows
    }

    /** Builds the "«years»: «name»" event row shared by every event query. */
    private fun eventRow(c: Cursor): SearchResult {
        val eventID = c.intAt(0)
        val name = c.str(1)
        val startYear = c.intAt(2)
        val endYear = c.intAt(3)
        val notes = c.strOpt(4) ?: ""
        val wiki = c.strOpt(5)
        val month = if (hasEventDates) c.intOpt(6) else null
        val day = if (hasEventDates) c.intOpt(7) else null

        val yearString = if (startYear == endYear) formatYear(startYear)
        else "${formatYear(startYear)}-${formatYear(endYear)}"
        return SearchResult(
            kind = ResultKind.EVENT, title = "$yearString: $name", subtitle = notes,
            wikipediaUrl = wikipediaLink(wiki, name),
            startYear = startYear, endYear = endYear, eventID = eventID,
            startMonth = month, startDay = day,
            iconAsset = "event",
        )
    }

    /** Events whose exact start date matches a calendar day — "On this day". */
    fun eventsOn(month: Int, day: Int): List<SearchResult> {
        if (!hasEventDates) return emptyList()
        val sql = """
            SELECT $eventColumns
            FROM byEvents e
            WHERE e.startMonth = ? AND e.startDay = ?
            ORDER BY e.startYear;
        """.trimIndent()
        val rows = ArrayList<SearchResult>()
        db.rawQuery(sql, arrayOf(month.toString(), day.toString())).use { c ->
            while (c.moveToNext()) rows += eventRow(c)
        }
        return rows
    }

    // MARK: - Discovery / favorites / quiz queries

    fun rulerById(id: Int): SearchResult? {
        val sql = """
            SELECT ru.rulerID, ru.name, ru.personal_name, ru.epithet, ru.wikipedia,
                   ru.biography, per.progrTitle, per.period, per.startYear, per.endYear,
                   per.notes, t.title, t.titlePlural${lifespanColumns("ru")}
            FROM rulers ru
            JOIN byPeriod per ON ru.rulerID = per.rulerID
            JOIN titles t ON per.titleID = t.titleID
            WHERE ru.rulerID = ?
            ORDER BY ru.rulerID, per.startYear;
        """.trimIndent()
        db.rawQuery(sql, arrayOf(id.toString())).use { c -> return collectRulerRows(c).firstOrNull() }
    }

    fun eventById(id: Int): SearchResult? {
        val sql = "SELECT $eventColumns FROM byEvents e WHERE e.eventID = ?;"
        db.rawQuery(sql, arrayOf(id.toString())).use { c ->
            return if (c.moveToNext()) eventRow(c) else null
        }
    }

    fun randomRuler(): SearchResult? {
        val sql = """
            SELECT DISTINCT ru.rulerID
            FROM rulers ru
            JOIN byPeriod per ON ru.rulerID = per.rulerID
            JOIN titles t ON per.titleID = t.titleID
            WHERE t.title NOT LIKE '%Consul%' AND t.title NOT LIKE '%Tribune%'
            ORDER BY RANDOM() LIMIT 1;
        """.trimIndent()
        db.rawQuery(sql, null).use { c ->
            if (!c.moveToNext()) return null
            return rulerById(c.intAt(0))
        }
    }

    fun randomEvent(): SearchResult? {
        val sql = "SELECT $eventColumns FROM byEvents e ORDER BY RANDOM() LIMIT 1;"
        db.rawQuery(sql, null).use { c ->
            return if (c.moveToNext()) eventRow(c) else null
        }
    }

    fun quizTitles(minHolders: Int = 15): List<TitleInfo> {
        val excluded = lifespanTitles.joinToString(", ") { "'$it'" }
        val sql = """
            SELECT titleID, title, titlePlural, maxCount FROM titles
            WHERE maxCount >= ? AND title NOT IN ($excluded) ORDER BY title;
        """.trimIndent()
        return titleInfos(sql, minHolders)
    }

    fun peopleTitles(minHolders: Int = 10): List<TitleInfo> {
        val included = lifespanTitles.joinToString(", ") { "'$it'" }
        val sql = """
            SELECT titleID, title, titlePlural, maxCount FROM titles
            WHERE maxCount >= ? AND title IN ($included) ORDER BY title;
        """.trimIndent()
        return titleInfos(sql, minHolders)
    }

    private fun titleInfos(sql: String, minHolders: Int): List<TitleInfo> {
        val rows = ArrayList<TitleInfo>()
        db.rawQuery(sql, arrayOf(minHolders.toString())).use { c ->
            while (c.moveToNext()) {
                rows += TitleInfo(
                    titleID = c.intAt(0), title = c.str(1),
                    titlePlural = c.strOpt(2), maxCount = c.intAt(3),
                )
            }
        }
        return rows
    }

    fun holders(ofTitle: String): List<HolderRow> {
        val sql = """
            SELECT ru.rulerID, ru.name, per.period, per.startYear, per.endYear, per.progrTitle
            FROM rulers ru
            JOIN byPeriod per ON ru.rulerID = per.rulerID
            JOIN titles t ON per.titleID = t.titleID
            WHERE t.title = ?
            ORDER BY per.progrTitle ASC;
        """.trimIndent()
        val rows = ArrayList<HolderRow>()
        db.rawQuery(sql, arrayOf(ofTitle)).use { c ->
            while (c.moveToNext()) {
                rows += HolderRow(
                    rulerID = c.intAt(0), name = c.str(1), period = c.str(2),
                    startYear = c.intAt(3), endYear = c.intAt(4), progrTitle = c.intAt(5),
                )
            }
        }
        return rows
    }

    /** The first and last year any holder of [title] reigned. */
    fun titleSpan(title: String): IntRange? {
        val sql = """
            SELECT MIN(per.startYear), MAX(per.endYear)
            FROM byPeriod per JOIN titles t ON per.titleID = t.titleID
            WHERE t.title = ?;
        """.trimIndent()
        db.rawQuery(sql, arrayOf(title)).use { c ->
            if (!c.moveToNext() || c.isNull(0)) return null
            val lo = c.intAt(0)
            val hi = c.intAt(1)
            return if (lo <= hi) lo..hi else null
        }
    }

    fun quizWorks(): List<WorkRow> {
        if (!tableExists("works")) return emptyList()
        val sql = """
            SELECT w.workTitle, w.year, w.category, w.creatorRulerID, ru.name
            FROM works w JOIN rulers ru ON w.creatorRulerID = ru.rulerID;
        """.trimIndent()
        val rows = ArrayList<WorkRow>()
        db.rawQuery(sql, null).use { c ->
            while (c.moveToNext()) {
                rows += WorkRow(
                    title = c.str(0), year = c.intAt(1), category = c.str(2),
                    creatorRulerID = c.intAt(3), creatorName = c.str(4),
                )
            }
        }
        return rows
    }

    fun randomQuizEvents(limit: Int): List<QuizEventRow> {
        val sql = "SELECT eventID, eventName, startYear, endYear FROM byEvents ORDER BY RANDOM() LIMIT ?;"
        val rows = ArrayList<QuizEventRow>()
        db.rawQuery(sql, arrayOf(limit.toString())).use { c ->
            while (c.moveToNext()) {
                rows += QuizEventRow(
                    eventID = c.intAt(0), name = c.str(1),
                    startYear = c.intAt(2), endYear = c.intAt(3),
                )
            }
        }
        return rows
    }

    fun isHealthy(): Boolean {
        db.rawQuery("SELECT COUNT(*) FROM rulers;", null).use { c ->
            return c.moveToNext() && c.intAt(0) > 0
        }
    }

    // MARK: - SQL helpers

    private fun yearClauseSQL(
        clause: QueryParser.YearClause, yearColumn: String,
    ): Pair<String, List<String>> = when (clause) {
        is QueryParser.YearClause.Range ->
            "($yearColumn BETWEEN ? AND ?)" to listOf(clause.lower.toString(), clause.upper.toString())
        is QueryParser.YearClause.Like ->
            "(CAST($yearColumn AS TEXT) LIKE ?)" to listOf(clause.pattern)
    }

    /** Builds `(colA LIKE ? OR colB LIKE ?) AND (...)` over the folded columns. */
    private fun foldedTextSQL(columns: List<String>, terms: List<String>): Pair<String, List<String>> {
        if (terms.isEmpty()) return "1=1" to emptyList()
        val conditions = ArrayList<String>()
        val params = ArrayList<String>()
        for (term in terms) {
            val parts = columns.joinToString(" OR ") { "$it LIKE ?" }
            conditions.add("($parts)")
            val folded = "%${foldForSearch(term)}%"
            repeat(columns.size) { params.add(folded) }
        }
        return conditions.joinToString(" AND ") to params
    }

    private fun wikipediaLink(stored: String?, name: String): String? {
        if (!stored.isNullOrEmpty()) return stored
        val slug = Uri.encode(name, "/")
        return "https://en.wikipedia.org/wiki/$slug"
    }

    companion object {
        /**
         * Titles whose "periods" are overlapping lifespans, not successive
         * reigns — kept out of ruler quiz questions.
         */
        val lifespanTitles = listOf("Artist", "Composer", "Writer", "Scientist", "Philosopher")
    }
}

// Cursor helpers matching the iOS typed column accessor.
private fun Cursor.intAt(i: Int): Int = getInt(i)
private fun Cursor.intOpt(i: Int): Int? = if (isNull(i)) null else getInt(i)
private fun Cursor.strOpt(i: Int): String? = if (isNull(i)) null else getString(i)
private fun Cursor.str(i: Int): String = if (isNull(i)) "" else getString(i)
