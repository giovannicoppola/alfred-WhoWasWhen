package com.giovannicoppola.whowaswhen.ui

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.StarOutline
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.giovannicoppola.whowaswhen.model.ResultKind
import com.giovannicoppola.whowaswhen.model.SearchResult

/**
 * The Favorites tab: saved rulers and events, newest first, rehydrated from
 * their database IDs so rows stay correct across database updates.
 */
@Composable
fun FavoritesScreen() {
    val vm = LocalAppActions.current.vm
    val entries by vm.favorites.entries.collectAsStateWithLifecycle()
    var results by remember { mutableStateOf<List<SearchResult>>(emptyList()) }
    var loaded by remember { mutableStateOf(false) }

    // Looks each saved ID back up in the database, dropping entries that no
    // longer resolve (e.g. removed in a data update).
    LaunchedEffect(entries) {
        val out = ArrayList<SearchResult>()
        for (e in entries) {
            val r = when (e.kind) {
                ResultKind.RULER -> vm.rulerById(e.dbID)
                ResultKind.EVENT -> vm.eventById(e.dbID)
            }
            if (r != null) out.add(r)
        }
        results = out
        loaded = true
    }

    IosScreen(navBar = { IosNavBar("Favorites") }) {
        if (results.isEmpty()) {
            if (loaded) {
                ContentUnavailable(
                    icon = Icons.Outlined.StarOutline,
                    title = "No favorites yet",
                    description = "Swipe a result — or tap the star in its details — to save rulers and events here.",
                )
            } else {
                IosSpinner(Modifier.align(Alignment.Center))
            }
        } else {
            val coordinator = remember { SwipeCoordinator() }
            val listState = rememberLazyListState()
            CompositionLocalProvider(LocalSwipeCoordinator provides coordinator) {
                CloseSwipesOnScroll(listState.isScrollInProgress)
                LazyColumn(state = listState, modifier = Modifier.fillMaxSize()) {
                    itemsIndexed(results, key = { _, r -> r.id }) { i, result ->
                        ResultRow(result = result, index = i, total = results.size)
                        IosDivider(startInset = 32.dp)
                    }
                }
            }
        }
    }
}
