package com.giovannicoppola.whowaswhen.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.gestures.scrollBy
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.outlined.AddComment
import androidx.compose.material.icons.outlined.EditCalendar
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.input.nestedscroll.NestedScrollConnection
import androidx.compose.ui.input.nestedscroll.NestedScrollSource
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.giovannicoppola.whowaswhen.R
import com.giovannicoppola.whowaswhen.model.SearchResult
import java.time.LocalDate
import java.time.format.TextStyle
import java.util.Locale

/**
 * Renders a list of results, or an appropriate empty state. When [yearHeader]
 * is set (a year search), the year is shown once as a pinned header instead of
 * being repeated on every row. [scrollToId] is centered once on appear (the
 * lineage view's focused ruler).
 */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun ResultsList(
    results: List<SearchResult>,
    isIdle: Boolean,
    yearHeader: String? = null,
    scrollToId: String? = null,
    listState: LazyListState = rememberLazyListState(),
) {
    if (results.isEmpty()) {
        if (isIdle) IdleHome() else ContentUnavailable(
            icon = Icons.Filled.Search,
            title = "No Results",
            description = "Check the spelling or try a new search.",
        )
        return
    }

    // Row indices are offset by one when the sticky year header is present.
    val headerOffset = if (yearHeader != null) 1 else 0
    CenterOnAppear(
        listState,
        scrollToId?.let { id -> results.indexOfFirst { it.id == id }.takeIf { it >= 0 }?.plus(headerOffset) },
    )
    val coordinator = remember { SwipeCoordinator() }
    CompositionLocalProvider(LocalSwipeCoordinator provides coordinator) {
        CloseSwipesOnScroll(listState.isScrollInProgress)
        LazyColumn(
            state = listState,
            modifier = Modifier
                .fillMaxSize()
                .dismissKeyboardOnDrag(),
        ) {
            if (yearHeader != null) {
                stickyHeader(key = "year-header") { YearHeader(yearHeader) }
            }
            itemsIndexed(results, key = { _, r -> r.id }) { idx, result ->
                ResultRow(result = result, index = idx, total = results.size)
                IosDivider(startInset = 32.dp)
            }
        }
    }
}

/**
 * `.scrollDismissesKeyboard(.immediately)`: flicking the results drops the
 * search keyboard so it stops covering the list.
 */
@Composable
fun Modifier.dismissKeyboardOnDrag(): Modifier {
    val keyboard = LocalSoftwareKeyboardController.current
    val focus = LocalFocusManager.current
    val connection = remember {
        object : NestedScrollConnection {
            override fun onPreScroll(available: Offset, source: NestedScrollSource): Offset {
                if (source == NestedScrollSource.UserInput && available.y != 0f) {
                    keyboard?.hide()
                    focus.clearFocus()
                }
                return Offset.Zero
            }
        }
    }
    return this.nestedScroll(connection)
}

/** Scrolls list item [targetIndex] to the vertical center once, when it first exists. */
@Composable
fun CenterOnAppear(listState: LazyListState, targetIndex: Int?) {
    var done by remember { mutableStateOf(false) }
    LaunchedEffect(targetIndex) {
        if (done || targetIndex == null || targetIndex < 0) return@LaunchedEffect
        listState.scrollToItem(targetIndex)
        val info = listState.layoutInfo
        val item = info.visibleItemsInfo.firstOrNull { it.index == targetIndex }
        if (item != null) {
            val viewport = info.viewportEndOffset - info.viewportStartOffset
            listState.scrollBy(-(viewport - item.size) / 2f)
        }
        done = true
    }
}

/** The pinned year banner at the top of year-search results. */
@Composable
private fun YearHeader(text: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Ios.colors.background)
            .padding(horizontal = 16.dp, vertical = 10.dp),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Filled.History, null, tint = Ios.colors.indigo, modifier = Modifier.size(24.dp))
        Text(
            text = text,
            style = Ios.type.title3.copy(fontWeight = FontWeight.Bold),
            color = Ios.colors.indigo,
        )
    }
}

/**
 * The home/empty state: the app logo, a search hint, and — when the database
 * knows an event dated today — an "On this day" card.
 */
@Composable
private fun IdleHome() {
    val actions = LocalAppActions.current
    var onThisDay by remember { mutableStateOf<SearchResult?>(null) }

    LaunchedEffect(Unit) {
        val matches = actions.vm.eventsOnToday()
        if (matches.isNotEmpty()) {
            // Several events can share today's date; rotate deterministically so
            // the card is stable within a day but varies across years.
            val today = LocalDate.now()
            val n = today.year + today.dayOfYear
            onThisDay = matches[n % matches.size]
        }
    }

    Column(
        modifier = Modifier.fillMaxSize().dismissKeyboardOnDrag(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.weight(1f))
        Image(
            painter = painterResource(R.drawable.app_logo),
            contentDescription = null,
            modifier = Modifier.size(104.dp),
        )
        Spacer(Modifier.height(18.dp))
        Text("WhoWasWhen", style = Ios.type.title2, color = Ios.colors.label)
        Spacer(Modifier.height(18.dp))
        Column(
            modifier = Modifier.padding(horizontal = 44.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            val hint = Ios.type.subheadline
            Text("Search:", style = hint, color = Ios.colors.secondaryLabel)
            Column(
                modifier = Modifier.padding(start = 20.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Text("a year (e.g. 1789, 177*, -44)", style = hint, color = Ios.colors.secondaryLabel)
                Text("a ruler", style = hint, color = Ios.colors.secondaryLabel)
                Text("or an event", style = hint, color = Ios.colors.secondaryLabel)
            }
        }
        onThisDay?.let {
            Spacer(Modifier.height(28.dp))
            OnThisDayCard(it)
        }
        Spacer(Modifier.weight(1f))
        HomeReportMenu()
        Spacer(Modifier.height(8.dp))
    }
}

/** "Report an issue or suggest data" — general feedback, by email or GitHub. */
@Composable
private fun HomeReportMenu() {
    var open by remember { mutableStateOf(false) }
    Box {
        Row(
            modifier = Modifier.iosClickable { open = true }.padding(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(Icons.Outlined.AddComment, null, tint = Ios.colors.accent, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(8.dp))
            Text("Report an issue or suggest data", style = Ios.type.footnote, color = Ios.colors.accent)
        }
        IosMenu(expanded = open, onDismiss = { open = false }) {
            ReportMenuItems(null, open = true, onToggle = {}, onDone = { open = false }, showHeader = false)
        }
    }
}

/** A tappable card highlighting an event that happened on today's date. */
@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun OnThisDayCard(result: SearchResult) {
    val actions = LocalAppActions.current
    val today = LocalDate.now()
    val dateLabel = "${today.month.getDisplayName(TextStyle.FULL, Locale.getDefault())} ${today.dayOfMonth}"
    var menuOpen by remember { mutableStateOf(false) }
    val source = remember { MutableInteractionSource() }

    Box(Modifier.padding(horizontal = 24.dp)) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(14.dp))
                .background(Ios.colors.secondaryBackground)
                .rowHighlight(source)
                .combinedClickable(
                    interactionSource = source,
                    indication = null,
                    onClick = { actions.showDetail(result) },
                    onLongClick = { actions.hapticLongPress(); menuOpen = true },
                )
                .padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.EditCalendar, null, tint = Ios.colors.indigo, modifier = Modifier.size(15.dp))
                Text(
                    "On this day — $dateLabel".uppercase(),
                    style = Ios.type.caption2.copy(fontWeight = FontWeight.Bold),
                    color = Ios.colors.indigo,
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                PortraitView(result = result, size = 44.dp)
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        result.title,
                        style = Ios.type.subheadline.copy(fontWeight = FontWeight.SemiBold),
                        color = Ios.colors.label,
                        maxLines = 2, overflow = TextOverflow.Ellipsis,
                    )
                    if (result.subtitle.isNotEmpty()) {
                        Text(
                            result.subtitle,
                            style = Ios.type.caption,
                            color = Ios.colors.secondaryLabel,
                            maxLines = 2, overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }
        }
        ResultContextMenu(result, expanded = menuOpen, onDismiss = { menuOpen = false })
    }
}
