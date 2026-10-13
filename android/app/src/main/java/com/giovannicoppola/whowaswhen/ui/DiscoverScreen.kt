package com.giovannicoppola.whowaswhen.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Shuffle
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.pulltorefresh.rememberPullToRefreshState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.giovannicoppola.whowaswhen.AnniversarySection
import com.giovannicoppola.whowaswhen.DiscoverState
import com.giovannicoppola.whowaswhen.WwwViewModel
import com.giovannicoppola.whowaswhen.model.SearchResult
import com.giovannicoppola.whowaswhen.model.formatNumber
import com.giovannicoppola.whowaswhen.model.formatYear
import kotlinx.coroutines.launch
import java.time.LocalDate

/**
 * The Discover tab: a shuffleable featured ruler + event, followed by
 * "centuries ago" anniversary sections. Mirrors iOS DiscoverView.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DiscoverScreen() {
    val vm = LocalAppActions.current.vm
    val st = vm.discover
    val c = Ios.colors
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        if (!st.loaded) {
            shuffle(vm, st)
            st.anniversaries = buildAnniversaries(vm)
            st.loaded = true
        }
    }

    IosScreen(
        background = c.groupedBackground,
        navBar = { IosNavBar("Discover", background = c.groupedBackground) },
    ) {
        val pullState = rememberPullToRefreshState()
        PullToRefreshBox(
            isRefreshing = st.refreshing,
            onRefresh = {
                scope.launch {
                    st.refreshing = true
                    shuffle(vm, st)
                    st.refreshing = false
                }
            },
            state = pullState,
            modifier = Modifier.fillMaxSize(),
            indicator = {
                // UIRefreshControl: the spinner fades in as you pull.
                if (st.refreshing || pullState.distanceFraction > 0f) {
                    IosSpinner(
                        Modifier
                            .align(Alignment.TopCenter)
                            .padding(top = 10.dp)
                            .graphicsLayer {
                                alpha = if (st.refreshing) 1f else pullState.distanceFraction.coerceIn(0f, 1f)
                            },
                    )
                }
            },
        ) {
            val coordinator = remember { SwipeCoordinator() }
            val listState = rememberLazyListState()
            CompositionLocalProvider(LocalSwipeCoordinator provides coordinator) {
                CloseSwipesOnScroll(listState.isScrollInProgress)
                LazyColumn(state = listState, modifier = Modifier.fillMaxSize()) {
                    if (st.loaded) {
                        item(key = "featured-header") { FeaturedHeader { scope.launch { shuffle(vm, st) } } }
                        item(key = "featured") {
                            GroupedCard {
                                st.featuredRuler?.let { FeaturedCard(it, featuredLabel(it)) }
                                if (st.featuredRuler != null && st.featuredEvent != null) IosDivider(20.dp)
                                st.featuredEvent?.let { FeaturedCard(it, "Featured event") }
                            }
                        }
                        items(st.anniversaries, key = { it.year }) { section ->
                            AnniversaryHeader(section)
                            GroupedCard {
                                ResultRow(
                                    result = section.result, index = 0, total = 1,
                                    showCounter = false, background = c.groupedCell,
                                )
                            }
                        }
                        item(key = "bottom") { Spacer(Modifier.height(28.dp)) }
                    }
                }
            }
        }
        if (!st.loaded) IosSpinner(Modifier.align(Alignment.Center))
    }
}

/** "FEATURED ………… ⤨ SURPRISE ME" — the section header with its shuffle button. */
@Composable
private fun FeaturedHeader(onShuffle: () -> Unit) {
    val c = Ios.colors
    Row(
        modifier = Modifier.fillMaxWidth().padding(start = 36.dp, end = 28.dp, top = 14.dp, bottom = 3.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text("FEATURED", style = Ios.type.footnote, color = c.secondaryLabel)
        Spacer(Modifier.weight(1f))
        Row(
            modifier = Modifier.iosClickable(onClick = onShuffle).padding(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(Icons.Filled.Shuffle, null, tint = c.accent, modifier = Modifier.size(16.dp))
            Spacer(Modifier.width(6.dp))
            Text(
                "SURPRISE ME",
                style = Ios.type.caption.copy(fontWeight = FontWeight.SemiBold),
                color = c.accent,
            )
        }
    }
}

@Composable
private fun AnniversaryHeader(section: AnniversarySection) {
    Row(
        modifier = Modifier.padding(start = 36.dp, end = 36.dp, top = 26.dp, bottom = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Icon(Icons.Filled.History, null, tint = Ios.colors.indigo, modifier = Modifier.size(18.dp))
        Text(
            "${formatNumber(section.yearsAgo)} years ago — ${formatYear(section.year)}",
            style = Ios.type.subheadline.copy(fontWeight = FontWeight.Bold),
            color = Ios.colors.indigo,
        )
    }
}

private suspend fun shuffle(vm: WwwViewModel, st: DiscoverState) {
    st.featuredRuler = vm.randomRuler()
    st.featuredEvent = vm.randomEvent()
}

/**
 * The featured "person" card can be a monarch, but also an artist, composer,
 * writer, scientist or philosopher — so label it with the person's actual
 * title rather than assuming "ruler".
 */
private fun featuredLabel(result: SearchResult): String {
    val title = result.titleName
    return if (!title.isNullOrEmpty()) "Featured $title" else "Featured person"
}

/**
 * Walks back a century at a time from the current year, keeping the first
 * centuries that have something to show. Each section surfaces a single
 * highlight — an event or a person from that year — chosen deterministically
 * from today's date, so the picks are stable through the day but rotate daily.
 */
private suspend fun buildAnniversaries(vm: WwwViewModel): List<AnniversarySection> {
    val today = LocalDate.now()
    val currentYear = today.year
    // Stable within a calendar day, changes daily.
    val daySeed = currentYear + today.dayOfYear

    val sections = ArrayList<AnniversarySection>()
    var yearsAgo = 100
    while (sections.size < 8 && currentYear - yearsAgo >= -776) {
        val year = currentYear - yearsAgo
        val events = vm.eventsInYear(year)
        // Events first (usually the more notable anniversaries); cap the rulers
        // so a year full of Roman consuls doesn't crowd the rotation.
        val rulers = vm.rulersInYear(year).take(6)
        val pool = events + rulers
        if (pool.isNotEmpty()) {
            // Offset per century so the sections don't all land on the same index.
            val pick = pool[((daySeed + yearsAgo) % pool.size + pool.size) % pool.size]
            sections.add(AnniversarySection(yearsAgo, year, pick))
        }
        yearsAgo += 100
    }
    return sections
}

/** A larger card for the featured ruler/event; tap opens the detail sheet. */
@Composable
fun FeaturedCard(result: SearchResult, kindLabel: String) {
    ResultActionsContainer(result, background = Ios.colors.groupedCell) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 17.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                kindLabel.uppercase(),
                style = Ios.type.caption2.copy(fontWeight = FontWeight.Bold),
                color = UiIcons.tint(result),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                PortraitView(result = result, size = 56.dp)
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(result.title, style = Ios.type.headline, color = Ios.colors.label)
                    if (result.subtitle.isNotEmpty()) {
                        Text(
                            result.subtitle,
                            style = Ios.type.subheadline,
                            color = Ios.colors.secondaryLabel,
                            maxLines = 3,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }
        }
    }
}
