package com.giovannicoppola.whowaswhen.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Help
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.giovannicoppola.whowaswhen.AppTab
import com.giovannicoppola.whowaswhen.Route
import com.giovannicoppola.whowaswhen.WwwViewModel
import com.giovannicoppola.whowaswhen.data.QueryParser
import com.giovannicoppola.whowaswhen.data.SearchScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private val Tabs = listOf(
    IosTab("Search", Icons.Filled.Search),
    IosTab("Discover", Icons.Filled.AutoAwesome),
    IosTab("Quiz", Icons.AutoMirrored.Filled.Help),
    IosTab("Favorites", Icons.Filled.Star),
)

/** Dismisses the detail sheet with its slide-down animation. */
val LocalDismissSheet = staticCompositionLocalOf<() -> Unit> { {} }

/** Shows the tabbed UI, or a clear error if the database failed to open. */
@Composable
fun WhoWasWhenApp(vm: WwwViewModel) {
    val context = LocalContext.current
    val view = LocalView.current
    val actions = remember(vm) { AppActions(vm, context, view) }
    val loadError by vm.loadError.collectAsStateWithLifecycle()

    CompositionLocalProvider(LocalAppActions provides actions) {
        val error = loadError
        if (error != null) {
            Box(Modifier.fillMaxSize().background(Ios.colors.background).statusBarsPadding()) {
                ContentUnavailable(Icons.Filled.Warning, "Couldn't open the database", error)
            }
            return@CompositionLocalProvider
        }

        // Each tab keeps its saved state (scroll positions, etc.) while hidden.
        val tabStates = rememberSaveableStateHolder()
        Column(Modifier.fillMaxSize().background(Ios.colors.background)) {
            Box(Modifier.weight(1f).fillMaxWidth()) {
                tabStates.SaveableStateProvider(vm.selectedTab.name) {
                    when (vm.selectedTab) {
                        AppTab.SEARCH -> SearchTab()
                        AppTab.DISCOVER -> DiscoverScreen()
                        AppTab.QUIZ -> QuizScreen()
                        AppTab.FAVORITES -> FavoritesScreen()
                    }
                }
                ToastHost(vm.toast, Modifier.matchParentSize())
            }
            IosTabBar(Tabs, vm.selectedTab.ordinal) { i ->
                val tab = AppTab.entries[i]
                // Re-tapping the selected Search tab pops to its root, as UITabBar does.
                if (tab == vm.selectedTab && tab == AppTab.SEARCH) vm.popToRoot()
                vm.selectedTab = tab
            }
        }

        // Android back: pop the Search stack, then leave search mode, then
        // return to the first tab, then exit.
        BackHandler(enabled = vm.selectedTab == AppTab.SEARCH && vm.path.isNotEmpty()) { vm.pop() }
        BackHandler(enabled = vm.selectedTab != AppTab.SEARCH) { vm.selectedTab = AppTab.SEARCH }

        vm.detail?.let { DetailSheetHost(vm, it) }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DetailSheetHost(vm: WwwViewModel, result: com.giovannicoppola.whowaswhen.model.SearchResult) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = false)
    val scope = rememberCoroutineScope()
    val dismiss: () -> Unit = {
        scope.launch { sheetState.hide() }.invokeOnCompletion { vm.hideDetail() }
    }
    ModalBottomSheet(
        onDismissRequest = { vm.hideDetail() },
        sheetState = sheetState,
        // Fully expanded, the sheet stops short of the status bar (the iOS
        // large detent leaves the presenting screen peeking out on top).
        modifier = Modifier.windowInsetsPadding(WindowInsets.statusBars).padding(top = 10.dp),
        containerColor = Ios.colors.groupedBackground,
        scrimColor = Color.Black.copy(alpha = 0.32f),
        shape = RoundedCornerShape(topStart = 12.dp, topEnd = 12.dp),
        dragHandle = null,
    ) {
        CompositionLocalProvider(LocalDismissSheet provides dismiss) {
            key(result.id) { ResultDetailContent(result) }
        }
    }
}

/**
 * A screen with an inline navigation bar whose background runs up under the
 * status bar, like a UINavigationBar's scroll-edge appearance.
 */
@Composable
fun IosScreen(
    background: Color = Ios.colors.background,
    navBar: @Composable () -> Unit,
    content: @Composable BoxScope.() -> Unit,
) {
    Column(Modifier.fillMaxSize().background(background)) {
        Column(Modifier.fillMaxWidth().background(background).statusBarsPadding()) { navBar() }
        Box(Modifier.weight(1f).fillMaxWidth(), content = content)
    }
}

// MARK: - Search tab (its own navigation stack)

/** The back button label: the previous screen's title, or "Back" if long/none. */
private fun backLabel(path: List<Route>, index: Int): String {
    val previous = if (index == 0) "WhoWasWhen" else when (val r = path[index - 1]) {
        is Route.Query -> "Back"
        is Route.Lineage -> r.title
    }
    return if (previous.length > 14) "Back" else previous
}

@Composable
private fun SearchTab() {
    val vm = LocalAppActions.current.vm
    val screens = rememberSaveableStateHolder()
    val top = vm.path.lastOrNull()

    AnimatedContent(
        targetState = top,
        transitionSpec = {
            val push = (targetState?.key ?: 0L) > (initialState?.key ?: 0L)
            val spec = tween<androidx.compose.ui.unit.IntOffset>(320)
            if (push) {
                slideInHorizontally(spec) { it } togetherWith slideOutHorizontally(spec) { -it / 3 }
            } else {
                slideInHorizontally(spec) { -it / 3 } togetherWith slideOutHorizontally(spec) { it }
            }
        },
        label = "searchStack",
    ) { route ->
        screens.SaveableStateProvider(route?.key ?: 0L) {
            when (route) {
                null -> SearchRoot()
                is Route.Query -> QueryResultsScreen(
                    query = route.query,
                    backLabel = backLabel(vm.path, vm.path.indexOf(route).coerceAtLeast(0)),
                    onBack = { vm.pop() },
                )
                is Route.Lineage -> LineageScreen(
                    title = route.title, rulerID = route.rulerID, prog = route.prog,
                    backLabel = backLabel(vm.path, vm.path.indexOf(route).coerceAtLeast(0)),
                    onBack = { vm.pop() },
                )
            }
        }
    }
}

/**
 * Root screen: a search box at the top with live results, mirroring the
 * Alfred workflow. Year jumps and "show all" push onto the tab's stack.
 */
@Composable
private fun SearchRoot() {
    val vm = LocalAppActions.current.vm
    val focusRequester = remember { FocusRequester() }
    val focusManager = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current

    // Debounced live search. Re-runs (and cancels in-flight work) when the
    // query or scope changes.
    LaunchedEffect(vm.query, vm.scope) {
        val q = vm.query.trim()
        if (q.isEmpty()) {
            vm.searchResults = emptyList()
            return@LaunchedEffect
        }
        delay(200)
        vm.searchResults = vm.results(q)
    }

    BackHandler(enabled = vm.searchActive) {
        vm.query = ""
        vm.searchActive = false
        focusManager.clearFocus()
    }

    Column(Modifier.fillMaxSize().background(Ios.colors.background)) {
        Column(Modifier.fillMaxWidth().statusBarsPadding()) {
            // While searching, the title slides away and Cancel + scopes appear.
            AnimatedVisibility(
                visible = !vm.searchActive,
                enter = expandVertically() + fadeIn(),
                exit = shrinkVertically() + fadeOut(),
            ) { IosNavBar("WhoWasWhen") }
            IosSearchField(
                query = vm.query,
                onQueryChange = { vm.query = it },
                placeholder = "Year, ruler, or event",
                active = vm.searchActive,
                onActivate = { vm.searchActive = true },
                onCancel = {
                    vm.query = ""
                    vm.searchActive = false
                    focusManager.clearFocus()
                    keyboard?.hide()
                },
                onSubmit = {
                    keyboard?.hide()
                    focusManager.clearFocus()
                },
                focusRequester = focusRequester,
            )
            AnimatedVisibility(
                visible = vm.searchActive,
                enter = expandVertically() + fadeIn(),
                exit = shrinkVertically() + fadeOut(),
            ) {
                IosTextSegments(
                    labels = SearchScope.entries.map { it.label },
                    selected = vm.scope.ordinal,
                    onSelect = { vm.scope = SearchScope.entries[it] },
                    modifier = Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 8.dp),
                )
            }
        }
        Box(Modifier.weight(1f).fillMaxWidth()) {
            ResultsList(
                results = vm.searchResults,
                isIdle = vm.query.isBlank(),
                yearHeader = QueryParser.displayYear(vm.query),
                listState = rememberLazyListState(),
            )
        }
    }
}
