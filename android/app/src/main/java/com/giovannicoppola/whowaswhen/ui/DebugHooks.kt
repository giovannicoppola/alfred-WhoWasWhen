package com.giovannicoppola.whowaswhen.ui

import android.content.Intent
import com.giovannicoppola.whowaswhen.AppTab
import com.giovannicoppola.whowaswhen.WwwViewModel

/**
 * Debug-build automation hooks — the Android twin of the iOS `WWW_*`
 * environment variables. Pass them as intent extras to jump straight to a
 * screen for screenshots or smoke tests, e.g.
 *
 *     adb shell am start -n com.giovannicoppola.whowaswhen/.MainActivity \
 *         --es WWW_QUERY 1789 --es WWW_DETAIL Washington
 *
 * Extras: WWW_TAB=discover|quiz|favorites, WWW_QUERY=<text>,
 * WWW_LINEAGE=<title>, WWW_TIMELINE=1, WWW_DETAIL=<title substring>,
 * WWW_QUIZ=1|events|rulers|people|works, WWW_ANSWER=1, WWW_SCORE=1,
 * WWW_CONFETTI=<seconds> (freeze the new-best confetti at that moment),
 * WWW_DARK=1|0. Release builds never read them.
 */
object DebugHooks {
    var timeline = false
    var answer = false
    var score = false
    var dark: Boolean? = null
    var confettiFreeze: Float? = null
    private var quiz: String? = null
    private var detail: String? = null

    fun read(intent: Intent?, vm: WwwViewModel) {
        val x = intent?.extras ?: return
        when (x.getString("WWW_TAB")) {
            "discover" -> vm.selectedTab = AppTab.DISCOVER
            "quiz" -> vm.selectedTab = AppTab.QUIZ
            "favorites" -> vm.selectedTab = AppTab.FAVORITES
        }
        x.getString("WWW_QUERY")?.let { vm.query = it }
        x.getString("WWW_LINEAGE")?.let { vm.showLineage(it) }
        timeline = x.getString("WWW_TIMELINE") != null
        quiz = x.getString("WWW_QUIZ")
        answer = x.getString("WWW_ANSWER") != null
        score = x.getString("WWW_SCORE") != null
        detail = x.getString("WWW_DETAIL")
        dark = x.getString("WWW_DARK")?.let { it == "1" }
        confettiFreeze = x.getString("WWW_CONFETTI")?.toFloatOrNull()
    }

    /** One-shot: the quiz category to start, consumed on first read. */
    fun takeQuiz(): String? = quiz.also { quiz = null }

    /** Opens the first search result whose title contains WWW_DETAIL. */
    suspend fun openDetailIfRequested(vm: WwwViewModel) {
        val want = detail ?: return
        detail = null
        val results = vm.results(vm.query.ifBlank { want })
        val pick = results.firstOrNull { it.title.contains(want, ignoreCase = true) } ?: results.firstOrNull()
        pick?.let { vm.showDetail(it) }
    }
}
