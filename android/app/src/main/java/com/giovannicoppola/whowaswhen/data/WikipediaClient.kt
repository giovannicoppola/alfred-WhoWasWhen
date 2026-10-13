package com.giovannicoppola.whowaswhen.data

import android.net.Uri
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject

/** The parts of a Wikipedia page summary the app uses. */
data class WikipediaSummary(
    val thumbnailUrl: String?,
    val extract: String?,
)

/**
 * Fetches page summaries (portrait thumbnail + first-paragraph extract) from
 * the Wikipedia REST API, keyed by the article URL stored in the database.
 * Results are cached in memory and de-duplicated while in flight; any failure
 * returns null and the UI falls back to the bundled biography — the app never
 * *requires* the network. Mirrors the iOS WikipediaClient.
 */
object WikipediaClient {
    private val client = OkHttpClient()
    private val cache = HashMap<String, WikipediaSummary>()
    private val inFlight = HashMap<String, Deferred<WikipediaSummary?>>()
    private val lock = Mutex()

    suspend fun summary(articleUrl: String): WikipediaSummary? = coroutineScope {
        lock.withLock { cache[articleUrl] }?.let { return@coroutineScope it }
        val running = lock.withLock { inFlight[articleUrl] }
        if (running != null) return@coroutineScope running.await()

        val task = async(Dispatchers.IO) { fetch(articleUrl) }
        lock.withLock { inFlight[articleUrl] = task }
        val value = task.await()
        lock.withLock {
            inFlight.remove(articleUrl)
            if (value != null) cache[articleUrl] = value
        }
        value
    }

    private fun fetch(articleUrl: String): WikipediaSummary? {
        val endpoint = summaryEndpoint(articleUrl) ?: return null
        val request = Request.Builder()
            .url(endpoint)
            .header(
                "User-Agent",
                "WhoWasWhen-Android/1.1 (https://github.com/giovannicoppola/alfred-WhoWasWhen)"
            )
            .build()

        return runCatching {
            client.newCall(request).execute().use { response ->
                if (response.code != 200) return null
                val body = response.body?.string() ?: return null
                val json = JSONObject(body)
                // A bare name can resolve to a disambiguation page; its extract
                // is a list of unrelated people, so drop it.
                val type = json.optString("type", "")
                val extract = if (type == "disambiguation") null
                else json.optString("extract", "").ifEmpty { null }
                val thumb = json.optJSONObject("thumbnail")?.optString("source")?.ifEmpty { null }
                WikipediaSummary(thumbnailUrl = thumb, extract = extract)
            }
        }.getOrNull()
    }

    /**
     * `…wikipedia.org/wiki/Julius_Caesar` → that host's
     * `/api/rest_v1/page/summary/Julius_Caesar`. Keeping the article's own host
     * means non-English links keep working.
     */
    fun summaryEndpoint(articleUrl: String): String? {
        val uri = runCatching { Uri.parse(articleUrl) }.getOrNull() ?: return null
        val host = uri.host ?: return null
        if (!host.endsWith("wikipedia.org")) return null
        val title = uri.lastPathSegment ?: return null
        if (title.isEmpty() || title == "/") return null
        val encoded = Uri.encode(title, "/")
        return "https://$host/api/rest_v1/page/summary/$encoded"
    }
}
