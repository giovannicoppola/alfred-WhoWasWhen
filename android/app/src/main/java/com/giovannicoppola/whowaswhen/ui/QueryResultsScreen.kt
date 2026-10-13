package com.giovannicoppola.whowaswhen.ui

import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.min
import com.giovannicoppola.whowaswhen.data.QueryParser
import com.giovannicoppola.whowaswhen.data.SearchScope
import com.giovannicoppola.whowaswhen.model.SearchResult

/**
 * A fixed-query screen reached by "travel to year" (always a year). Runs the
 * query under a pinned year header, with a scope selector in the navigation
 * bar so the All / People / Events filter is available here too. Back returns
 * to the previous screen, like the workflow's "go back to main search".
 */
@Composable
fun QueryResultsScreen(query: String, backLabel: String, onBack: () -> Unit) {
    val vm = LocalAppActions.current.vm
    var results by remember { mutableStateOf<List<SearchResult>>(emptyList()) }
    var loaded by remember { mutableStateOf(false) }

    // Re-runs on first appearance and whenever the scope changes.
    LaunchedEffect(vm.scope) {
        results = vm.results(query)
        loaded = true
    }

    IosScreen(
        navBar = {
            BoxWithConstraints(Modifier.fillMaxWidth()) {
                val maxWidth = this.maxWidth
                // The principal picker takes the middle (max 260pt); the back
                // button collapses to its chevron, as UIKit does when space is tight.
                val pickerWidth = min(260.dp, maxWidth - 120.dp)
                IosNavBar(
                    title = "",
                    leading = { IosBackButton(if (maxWidth - pickerWidth > 300.dp) backLabel else "", onBack) },
                    center = {
                        IosTextSegments(
                            labels = SearchScope.entries.map { it.label },
                            selected = vm.scope.ordinal,
                            onSelect = { vm.scope = SearchScope.entries[it] },
                            modifier = Modifier.width(pickerWidth),
                        )
                    },
                )
            }
        },
    ) {
        val listState = rememberLazyListState()
        if (loaded) {
            ResultsList(
                results = results,
                isIdle = false,
                yearHeader = QueryParser.displayYear(query) ?: query,
                listState = listState,
            )
        } else {
            IosSpinner(Modifier.align(Alignment.Center))
        }
    }
}
