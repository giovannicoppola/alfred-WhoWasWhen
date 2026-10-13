package com.giovannicoppola.whowaswhen.ui

import android.net.Uri
import com.giovannicoppola.whowaswhen.BuildConfig
import com.giovannicoppola.whowaswhen.model.ResultKind
import com.giovannicoppola.whowaswhen.model.SearchResult

/**
 * Builds pre-filled "report an issue" links (email + GitHub) so users can flag
 * data errors. No data is collected or transmitted by the app — the user
 * composes and sends from their own mail/browser. Mirrors the iOS Reporting.
 */
object Reporting {
    const val EMAIL = "giovannicoppola@gmail.com"
    const val REPO = "https://github.com/giovannicoppola/alfred-WhoWasWhen"
    val APP_VERSION = "${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})"

    private fun subjectAndBody(result: SearchResult?): Pair<String, String> {
        var subject = "WhoWasWhen feedback or data suggestion"
        val lines = ArrayList<String>()
        if (result != null) {
            subject = "WhoWasWhen data issue: ${result.title}"
            lines.add("Entry: ${result.title}")
            if (result.subtitle.isNotEmpty()) lines.add("Details: ${result.subtitle}")
            lines.add("Type: ${if (result.kind == ResultKind.RULER) "Ruler" else "Event"}")
            result.rulerID?.let { id ->
                var ref = "rulerID=$id"
                result.progrTitle?.let { ref += ", progrTitle=$it" }
                result.titleName?.takeIf { it.isNotEmpty() }?.let { ref += ", title=$it" }
                lines.add("Reference: $ref")
            }
        }
        lines.add("App: WhoWasWhen $APP_VERSION")
        lines.add("")
        if (result == null) {
            lines.add("Report an issue, or suggest additional rulers, events, or other data to include:")
        } else {
            lines.add("Describe the problem:")
        }
        lines.add("")
        return subject to lines.joinToString("\n")
    }

    fun emailUrl(result: SearchResult?): String {
        val (subject, body) = subjectAndBody(result)
        return "mailto:$EMAIL?subject=${Uri.encode(subject)}&body=${Uri.encode(body)}"
    }

    fun githubUrl(result: SearchResult?): String {
        val (subject, body) = subjectAndBody(result)
        return "$REPO/issues/new?title=${Uri.encode(subject)}&body=${Uri.encode(body)}"
    }
}
