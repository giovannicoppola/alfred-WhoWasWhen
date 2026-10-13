package com.giovannicoppola.whowaswhen

import android.app.Application
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.giovannicoppola.whowaswhen.data.Database
import com.giovannicoppola.whowaswhen.data.DatabaseProvider
import com.giovannicoppola.whowaswhen.data.FavoritesStore
import com.giovannicoppola.whowaswhen.data.QuizCategory
import com.giovannicoppola.whowaswhen.data.QuizQuestion
import com.giovannicoppola.whowaswhen.data.QuizStats
import com.giovannicoppola.whowaswhen.data.SearchScope
import com.giovannicoppola.whowaswhen.model.HolderRow
import com.giovannicoppola.whowaswhen.model.QuizEventRow
import com.giovannicoppola.whowaswhen.model.SearchResult
import com.giovannicoppola.whowaswhen.model.TitleInfo
import com.giovannicoppola.whowaswhen.model.WorkRow
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.LocalDate

/**
 * A pushable screen on the Search tab's stack. `Query` powers "travel to
 * year"; `Lineage` powers "Show all «title»". Back == the workflow's "go back
 * to main search". [key] keeps each pushed instance's saved state separate.
 */
sealed interface Route {
    val key: Long

    data class Query(val query: String, override val key: Long) : Route
    data class Lineage(
        val title: String, val rulerID: Int?, val prog: Int?, override val key: Long,
    ) : Route
}

/** The app's top-level tabs. */
enum class AppTab { SEARCH, DISCOVER, QUIZ, FAVORITES }

/** One "N years ago" Discover section. */
data class AnniversarySection(val yearsAgo: Int, val year: Int, val result: SearchResult)

/** Discover tab state, kept here so it survives tab switches (as iOS TabView does). */
class DiscoverState {
    var featuredRuler by mutableStateOf<SearchResult?>(null)
    var featuredEvent by mutableStateOf<SearchResult?>(null)
    var anniversaries by mutableStateOf<List<AnniversarySection>>(emptyList())
    var loaded by mutableStateOf(false)
    var refreshing by mutableStateOf(false)
}

/** Quiz tab state — a round in progress survives switching tabs. */
class QuizState {
    enum class Phase { PICKING, LOADING, PLAYING, FINISHED }

    var phase by mutableStateOf(Phase.PICKING)
    var category by mutableStateOf<QuizCategory>(QuizCategory.Mixed)
    var titles by mutableStateOf<List<TitleInfo>>(emptyList())
    var orderedTitles by mutableStateOf<List<TitleInfo>>(emptyList())
    var hasPeople by mutableStateOf(false)
    var hasWorks by mutableStateOf(false)
    var questions by mutableStateOf<List<QuizQuestion>>(emptyList())
    var index by mutableStateOf(0)
    var selection by mutableStateOf<Int?>(null)
    var score by mutableStateOf(0)
    var newBest by mutableStateOf(false)
    var titlesLoaded = false
}

/**
 * App-wide state and data access — the Android counterpart of the iOS
 * `AppModel` + `FavoritesStore`. Holds the open database, the selected tab and
 * the Search tab's navigation path, the search scope, per-tab screen state,
 * the favorites store, quiz stats, and the transient toast + detail sheet.
 * All database work runs on [Dispatchers.IO].
 */
class WwwViewModel(app: Application) : AndroidViewModel(app) {

    val favorites = FavoritesStore(app)
    val stats = QuizStats(app)

    private val dbReady = CompletableDeferred<Database?>()
    private val _loadError = MutableStateFlow<String?>(null)
    val loadError: StateFlow<String?> = _loadError

    // Navigation (mirrors AppModel.selectedTab / AppModel.path).
    var selectedTab by mutableStateOf(AppTab.SEARCH)
    val path = mutableStateListOf<Route>()
    private var nextRouteKey = 1L

    var scope by mutableStateOf(SearchScope.ALL)

    // Search tab.
    var query by mutableStateOf("")
    var searchActive by mutableStateOf(false)
    var searchResults by mutableStateOf<List<SearchResult>>(emptyList())

    val discover = DiscoverState()
    val quiz = QuizState()

    var toast by mutableStateOf<String?>(null)
        private set
    private var toastJob: Job? = null

    var detail by mutableStateOf<SearchResult?>(null)
        private set

    init {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val path = DatabaseProvider.resolveDatabasePath(getApplication())
                val db = Database(path)
                if (db.isHealthy()) {
                    dbReady.complete(db)
                } else {
                    _loadError.value = "The database opened but is not usable."
                    dbReady.complete(null)
                }
            } catch (e: Exception) {
                _loadError.value = e.toString()
                dbReady.complete(null)
            }
        }
    }

    private suspend fun db(): Database? = dbReady.await()

    // MARK: - Navigation

    // Both push onto the Search tab's stack, so jump to that tab first when
    // invoked from Discover / Favorites — otherwise the push is invisible.
    // Use the raw signed year (e.g. "-44") so the parser reads it as a year.
    fun travel(toYear: Int) {
        selectedTab = AppTab.SEARCH
        path.add(Route.Query(toYear.toString(), nextRouteKey++))
    }

    fun showLineage(result: SearchResult) {
        val title = result.titleName
        if (title.isNullOrEmpty()) return
        selectedTab = AppTab.SEARCH
        path.add(Route.Lineage(title, result.rulerID, result.progrTitle, nextRouteKey++))
    }

    fun showLineage(title: String) {
        selectedTab = AppTab.SEARCH
        path.add(Route.Lineage(title, null, null, nextRouteKey++))
    }

    fun pop() {
        if (path.isNotEmpty()) path.removeAt(path.lastIndex)
    }

    fun popToRoot() = path.clear()

    // MARK: - Search / lineage

    suspend fun results(query: String): List<SearchResult> = withContext(Dispatchers.IO) {
        db()?.search(query, scope) ?: emptyList()
    }

    suspend fun lineageResults(title: String, rulerID: Int?, prog: Int?): List<SearchResult> =
        withContext(Dispatchers.IO) { db()?.lineage(title, rulerID, prog) ?: emptyList() }

    // MARK: - Discover / favorites data

    suspend fun randomRuler(): SearchResult? = withContext(Dispatchers.IO) { db()?.randomRuler() }
    suspend fun randomEvent(): SearchResult? = withContext(Dispatchers.IO) { db()?.randomEvent() }

    suspend fun eventsInYear(year: Int): List<SearchResult> = withContext(Dispatchers.IO) {
        db()?.searchByYear(year.toString(), emptyList(), includeRulers = false, includeEvents = true)
            ?: emptyList()
    }

    suspend fun rulersInYear(year: Int): List<SearchResult> = withContext(Dispatchers.IO) {
        db()?.searchByYear(year.toString(), emptyList(), includeRulers = true, includeEvents = false)
            ?: emptyList()
    }

    suspend fun rulerById(id: Int): SearchResult? = withContext(Dispatchers.IO) { db()?.rulerById(id) }
    suspend fun eventById(id: Int): SearchResult? = withContext(Dispatchers.IO) { db()?.eventById(id) }

    suspend fun eventsOnToday(): List<SearchResult> = withContext(Dispatchers.IO) {
        val today = LocalDate.now()
        db()?.eventsOn(today.monthValue, today.dayOfMonth) ?: emptyList()
    }

    // MARK: - Quiz data

    suspend fun quizTitles(): List<TitleInfo> = withContext(Dispatchers.IO) { db()?.quizTitles() ?: emptyList() }
    suspend fun peopleTitles(): List<TitleInfo> = withContext(Dispatchers.IO) { db()?.peopleTitles() ?: emptyList() }
    suspend fun quizWorks(): List<WorkRow> = withContext(Dispatchers.IO) { db()?.quizWorks() ?: emptyList() }
    suspend fun holders(ofTitle: String): List<HolderRow> = withContext(Dispatchers.IO) { db()?.holders(ofTitle) ?: emptyList() }
    suspend fun titleSpan(title: String): IntRange? = withContext(Dispatchers.IO) { db()?.titleSpan(title) }
    suspend fun randomQuizEvents(limit: Int): List<QuizEventRow> = withContext(Dispatchers.IO) { db()?.randomQuizEvents(limit) ?: emptyList() }

    /** The open database, for the quiz engine (which does its own IO calls). */
    suspend fun database(): Database? = db()

    // MARK: - Detail sheet, toast, favorites, clipboard

    fun showDetail(result: SearchResult) { detail = result }
    fun hideDetail() { detail = null }

    /** Shows a transient banner that auto-dismisses after a short delay. */
    fun showToast(message: String) {
        toast = message
        toastJob?.cancel()
        toastJob = viewModelScope.launch {
            delay(1600)
            toast = null
        }
    }

    /** Toggles favorite state and confirms with a toast. */
    fun toggleFavorite(result: SearchResult) {
        val nowSaved = favorites.toggle(result) ?: return
        showToast(if (nowSaved) "Added to Favorites" else "Removed from Favorites")
    }

    fun copyToClipboard(result: SearchResult) {
        val clipboard = getApplication<Application>()
            .getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("WhoWasWhen", result.copyText))
        showToast("Copied to clipboard")
    }
}
