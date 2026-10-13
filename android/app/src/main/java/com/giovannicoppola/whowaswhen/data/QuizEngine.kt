package com.giovannicoppola.whowaswhen.data

import com.giovannicoppola.whowaswhen.model.HolderRow
import com.giovannicoppola.whowaswhen.model.QuizEventRow
import com.giovannicoppola.whowaswhen.model.TitleInfo
import com.giovannicoppola.whowaswhen.model.WorkRow
import com.giovannicoppola.whowaswhen.model.formatYear
import com.giovannicoppola.whowaswhen.model.titlePluralOrDefault
import java.time.Year
import java.util.UUID
import kotlin.math.abs
import kotlin.random.Random

/** The subject a question is about, so the reveal can link to the detail view. */
sealed interface SubjectID {
    data class Ruler(val rulerID: Int) : SubjectID
    data class Event(val eventID: Int) : SubjectID
}

/** One multiple-choice question, fully self-contained. */
data class QuizQuestion(
    val prompt: String,
    /** Second prompt line — the event/person name for those question types. */
    val subject: String? = null,
    val options: List<String>,
    val correctIndex: Int,
    /** Shown after answering, e.g. "Julius Caesar — Roman Consul (59 BC)". */
    val explanation: String,
    val subjectID: SubjectID? = null,
    /** Year options read better centered; names stay leading-aligned. */
    val centerOptions: Boolean = false,
    val id: String = UUID.randomUUID().toString(),
)

/** What a round draws its questions from. */
sealed interface QuizCategory {
    data object Mixed : QuizCategory
    data object Rulers : QuizCategory
    data object Events : QuizCategory
    data object People : QuizCategory
    data object Works : QuizCategory
    data class Title(val info: TitleInfo) : QuizCategory

    val id: String
        get() = when (this) {
            Mixed -> "mixed"
            Rulers -> "rulers"
            Events -> "events"
            People -> "people"
            Works -> "works"
            is Title -> "title-${info.titleID}"
        }

    val label: String
        get() = when (this) {
            Mixed -> "Mixed"
            Rulers -> "Rulers"
            Events -> "Events"
            People -> "Notable people"
            Works -> "Works & authors"
            is Title -> titlePluralOrDefault(info.titlePlural, info.title)
        }
}

/**
 * Generates quiz rounds from the database — every question and every wrong
 * answer is real data, so the quiz works fully offline. All DB access is
 * synchronous; callers invoke [buildRound] on a background dispatcher.
 */
object QuizEngine {
    const val ROUND_SIZE = 10

    private fun currentYear(): Int = Year.now().value

    fun buildRound(category: QuizCategory, db: Database): List<QuizQuestion> {
        return when (category) {
            is QuizCategory.Events -> {
                val events = db.randomQuizEvents(ROUND_SIZE * 3)
                eventQuestions(events, ROUND_SIZE)
            }

            is QuizCategory.Title -> {
                val t = category.info
                val holders = db.holders(t.title)
                if (Database.lifespanTitles.contains(t.title)) {
                    val works = db.quizWorks().filter { it.category == t.title }
                    val qs = ArrayList(workQuestions(works, ROUND_SIZE / 2))
                    val people = holders.map { t.title to it }.shuffled()
                    qs += peopleQuestions(people, ROUND_SIZE - qs.size, singleCalling = true)
                    qs.shuffled()
                } else {
                    rulerQuestions(t, holders, ROUND_SIZE)
                }
            }

            is QuizCategory.Rulers -> {
                val titles = db.quizTitles().shuffled()
                rulerRound(titles, ROUND_SIZE, db).shuffled()
            }

            is QuizCategory.People -> {
                peopleQuestions(notablePeople(db), ROUND_SIZE)
            }

            is QuizCategory.Works -> {
                workQuestions(db.quizWorks(), ROUND_SIZE)
            }

            is QuizCategory.Mixed -> {
                val titles = db.quizTitles().shuffled()
                if (titles.isEmpty()) return emptyList()
                val eventTarget = ROUND_SIZE / 3
                val events = db.randomQuizEvents(eventTarget * 3)
                val questions = ArrayList(eventQuestions(events, eventTarget))
                questions += peopleQuestions(notablePeople(db), ROUND_SIZE / 5)
                questions += workQuestions(db.quizWorks(), ROUND_SIZE / 5)
                questions += rulerRound(titles, ROUND_SIZE - questions.size, db)
                questions.shuffled()
            }
        }
    }

    /** Every holder of a lifespan title, tagged with it — the People pool. */
    private fun notablePeople(db: Database): List<Pair<String, HolderRow>> {
        val people = ArrayList<Pair<String, HolderRow>>()
        for (title in Database.lifespanTitles) {
            for (h in db.holders(title)) people.add(title to h)
        }
        return people.shuffled()
    }

    /** Ruler questions spread over random titles (the Mixed and Rulers rounds). */
    private fun rulerRound(titles: List<TitleInfo>, count: Int, db: Database): List<QuizQuestion> {
        if (titles.isEmpty() || count <= 0) return emptyList()
        val questions = ArrayList<QuizQuestion>()
        var i = 0
        while (questions.size < count && i < count * 3) {
            val t = titles[i % titles.size]
            val holders = db.holders(t.title)
            questions += rulerQuestions(t, holders, 1)
            i++
        }
        return questions
    }

    // MARK: - Ruler questions

    fun rulerQuestions(title: TitleInfo, holders: List<HolderRow>, count: Int): List<QuizQuestion> {
        if (holders.size < 6) return emptyList()
        val out = ArrayList<QuizQuestion>()
        var attempts = 0
        while (out.size < count && attempts < count * 10) {
            attempts++
            val q = if (Random.nextBoolean()) whoWasQuestion(title, holders)
            else whenWasQuestion(title, holders)
            if (q != null && out.none { it.prompt == q.prompt }) out.add(q)
        }
        return out
    }

    private fun whoWasQuestion(title: TitleInfo, holders: List<HolderRow>): QuizQuestion? {
        val h = holders.randomOrNull() ?: return null
        if (h.startYear > h.endYear) return null
        val year = Random.nextInt(h.startYear, h.endYear + 1)

        val others = holders.filter { it.name != h.name && (it.endYear < year || it.startYear > year) }
        val nearest = others.sortedBy { abs(it.progrTitle - h.progrTitle) }
        val wrongNames = ArrayList<String>()
        for (cand in nearest.take(24).shuffled()) {
            if (wrongNames.size >= 3) break
            if (!wrongNames.contains(cand.name)) wrongNames.add(cand.name)
        }
        if (wrongNames.size != 3) return null

        val options = (wrongNames + h.name).shuffled()
        return QuizQuestion(
            prompt = "Who was ${title.title} in ${formatYear(year)}?",
            options = options,
            correctIndex = options.indexOf(h.name),
            explanation = "${h.name} — ${title.title} (${h.period})",
            subjectID = SubjectID.Ruler(h.rulerID),
        )
    }

    private fun whenWasQuestion(title: TitleInfo, holders: List<HolderRow>): QuizQuestion? {
        val h = holders.randomOrNull() ?: return null

        val others = holders.filter {
            it.period != h.period && (it.endYear < h.startYear || it.startYear > h.endYear)
        }
        val nearest = others.sortedBy { abs(it.progrTitle - h.progrTitle) }
        val wrongPeriods = ArrayList<String>()
        for (cand in nearest.take(24).shuffled()) {
            if (wrongPeriods.size >= 3) break
            if (!wrongPeriods.contains(cand.period)) wrongPeriods.add(cand.period)
        }
        if (wrongPeriods.size != 3) return null

        val options = (wrongPeriods + h.period).shuffled()
        return QuizQuestion(
            prompt = "When was ${h.name} ${title.title}?",
            options = options,
            correctIndex = options.indexOf(h.period),
            explanation = "${h.name} — ${title.title} (${h.period})",
            subjectID = SubjectID.Ruler(h.rulerID),
            centerOptions = true,
        )
    }

    // MARK: - Notable-people questions

    fun peopleQuestions(
        people: List<Pair<String, HolderRow>>, count: Int, singleCalling: Boolean = false,
    ): List<QuizQuestion> {
        val out = ArrayList<QuizQuestion>()
        for ((category, person) in people) {
            if (out.size >= count) break
            val q = if (!singleCalling && Random.nextInt(0, 3) == 0) {
                whatWasQuestion(category, person)
            } else {
                lifeYearQuestion(category, person)
            }
            if (q != null && out.none { it.subject == q.subject }) out.add(q)
        }
        return out
    }

    private fun lifeYearQuestion(category: String, person: HolderRow): QuizQuestion? {
        val asksDeath = Random.nextBoolean()
        val correct = if (asksDeath) person.endYear else person.startYear
        if (person.startYear >= person.endYear) return null
        if (person.name.contains(abs(correct).toString())) return null
        val currentYear = currentYear()

        val years = linkedSetOf(correct)
        var attempts = 0
        val magnitudes = listOf(2..8, 10..30, 40..90)
        while (years.size < 4 && attempts < 40) {
            attempts++
            val magnitude = magnitudes.random()
            val offset = magnitude.random()
            val y = if (Random.nextBoolean()) correct + offset else correct - offset
            if (y <= currentYear) years.add(y)
        }
        if (years.size != 4) return null

        val sorted = years.sorted()
        return QuizQuestion(
            prompt = if (asksDeath) "When did this person die?" else "When was this person born?",
            subject = person.name,
            options = sorted.map { formatYear(it) },
            correctIndex = sorted.indexOf(correct),
            explanation = "${person.name} — $category (${person.period})",
            subjectID = SubjectID.Ruler(person.rulerID),
            centerOptions = true,
        )
    }

    private fun whatWasQuestion(category: String, person: HolderRow): QuizQuestion? {
        val others = Database.lifespanTitles.filter { it != category }.shuffled()
        if (others.size < 3) return null
        val options = (others.take(3) + category).shuffled()
        return QuizQuestion(
            prompt = "What was this person?",
            subject = person.name,
            options = options,
            correctIndex = options.indexOf(category),
            explanation = "${person.name} — $category (${person.period})",
            subjectID = SubjectID.Ruler(person.rulerID),
            centerOptions = true,
        )
    }

    // MARK: - Works & authors questions

    private fun creationClause(category: String, work: String): String = when (category) {
        "Composer" -> "composed $work"
        "Artist" -> "created $work"
        "Scientist" -> "is known for $work"
        else -> "wrote $work" // Writer, Philosopher
    }

    fun workQuestions(works: List<WorkRow>, count: Int): List<QuizQuestion> {
        if (works.size < 4) return emptyList()
        val out = ArrayList<QuizQuestion>()
        for (w in works.shuffled()) {
            if (out.size >= count) break
            val title = w.title.lowercase()
            val sameTitle = works.filter { it.title.lowercase() == title }.map { it.creatorRulerID }.toSet()
            val sameKind = works.filter { it.category == w.category && !sameTitle.contains(it.creatorRulerID) }
            val nearest = sameKind.sortedBy { abs(it.year - w.year) }
            val wrong = ArrayList<String>()
            for (cand in nearest.take(20).shuffled()) {
                if (wrong.size >= 3) break
                if (cand.creatorName != w.creatorName && !wrong.contains(cand.creatorName)) {
                    wrong.add(cand.creatorName)
                }
            }
            if (wrong.size != 3) continue
            if (out.any { it.subjectID == SubjectID.Ruler(w.creatorRulerID) }) continue

            val options = (wrong + w.creatorName).shuffled()
            out.add(
                QuizQuestion(
                    prompt = "Who ${creationClause(w.category, w.title)}?",
                    options = options,
                    correctIndex = options.indexOf(w.creatorName),
                    explanation = "${w.title} — ${w.creatorName} (${formatYear(w.year)})",
                    subjectID = SubjectID.Ruler(w.creatorRulerID),
                )
            )
        }
        return out
    }

    // MARK: - Event questions

    fun eventQuestions(events: List<QuizEventRow>, count: Int): List<QuizQuestion> {
        val out = ArrayList<QuizQuestion>()
        for (e in events) {
            if (out.size >= count) break
            val q = eventQuestion(e)
            if (q != null && out.none { it.subject == q.subject }) out.add(q)
        }
        return out
    }

    private fun eventQuestion(e: QuizEventRow): QuizQuestion? {
        val asksEnd = e.startYear != e.endYear && Random.nextBoolean()
        val correct = if (asksEnd) e.endYear else e.startYear
        if (e.name.contains(abs(correct).toString())) return null
        val currentYear = currentYear()

        val years = linkedSetOf(correct)
        var attempts = 0
        val magnitudes = listOf(3..9, 10..40, 50..150)
        while (years.size < 4 && attempts < 40) {
            attempts++
            val magnitude = magnitudes.random()
            val offset = magnitude.random()
            val y = if (Random.nextBoolean()) correct + offset else correct - offset
            if (y <= currentYear) years.add(y)
        }
        if (years.size != 4) return null

        val sorted = years.sorted()
        val verb = if (e.startYear == e.endYear) "happen" else if (asksEnd) "end" else "begin"
        val answer = if (e.startYear == e.endYear) formatYear(e.startYear)
        else "${formatYear(e.startYear)}-${formatYear(e.endYear)}"
        return QuizQuestion(
            prompt = "When did this $verb?",
            subject = e.name,
            options = sorted.map { formatYear(it) },
            correctIndex = sorted.indexOf(correct),
            explanation = "${e.name} — $answer",
            subjectID = SubjectID.Event(e.eventID),
            centerOptions = true,
        )
    }
}
