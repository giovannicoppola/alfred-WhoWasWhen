package com.giovannicoppola.whowaswhen.data

import android.content.Context
import com.giovannicoppola.whowaswhen.model.ResultKind
import com.giovannicoppola.whowaswhen.model.SearchResult
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** A saved ruler or event, keyed by its stable database ID. */
data class FavoriteEntry(
    val kind: ResultKind,
    val dbID: Int,
    val dateAdded: Long,
) {
    val id: String get() = "${kind.name}-$dbID"
}

/**
 * The user's favorites, persisted as a small JSON file in internal storage
 * (a handful of IDs — no need for a database). Mirrors the iOS FavoritesStore.
 */
class FavoritesStore(context: Context) {
    private val file = File(context.filesDir, "favorites.json")

    private val _entries = MutableStateFlow<List<FavoriteEntry>>(emptyList())
    /** Newest first. */
    val entries: StateFlow<List<FavoriteEntry>> = _entries

    init {
        load()
    }

    fun isFavorite(result: SearchResult): Boolean {
        val (kind, dbID) = identity(result) ?: return false
        return _entries.value.any { it.kind == kind && it.dbID == dbID }
    }

    /**
     * Adds or removes a favorite. Returns the new state (true = now saved),
     * or null if the result has no stable identity.
     */
    fun toggle(result: SearchResult): Boolean? {
        val (kind, dbID) = identity(result) ?: return null
        val current = _entries.value
        val existing = current.indexOfFirst { it.kind == kind && it.dbID == dbID }
        return if (existing >= 0) {
            _entries.value = current.toMutableList().apply { removeAt(existing) }
            save()
            false
        } else {
            _entries.value = listOf(FavoriteEntry(kind, dbID, System.currentTimeMillis())) + current
            save()
            true
        }
    }

    fun remove(entry: FavoriteEntry) {
        _entries.value = _entries.value.filterNot { it == entry }
        save()
    }

    private fun identity(result: SearchResult): Pair<ResultKind, Int>? = when (result.kind) {
        ResultKind.RULER -> result.rulerID?.let { ResultKind.RULER to it }
        ResultKind.EVENT -> result.eventID?.let { ResultKind.EVENT to it }
    }

    // MARK: - Persistence

    private fun load() {
        if (!file.exists()) return
        runCatching {
            val text = file.readText()
            val arr = JSONArray(text)
            val out = ArrayList<FavoriteEntry>(arr.length())
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i)
                out.add(
                    FavoriteEntry(
                        kind = ResultKind.valueOf(o.getString("kind")),
                        dbID = o.getInt("dbID"),
                        dateAdded = o.getLong("dateAdded"),
                    )
                )
            }
            _entries.value = out
        }
    }

    private fun save() {
        val arr = JSONArray()
        for (e in _entries.value) {
            arr.put(
                JSONObject()
                    .put("kind", e.kind.name)
                    .put("dbID", e.dbID)
                    .put("dateAdded", e.dateAdded)
            )
        }
        runCatching { file.writeText(arr.toString()) }
    }
}
