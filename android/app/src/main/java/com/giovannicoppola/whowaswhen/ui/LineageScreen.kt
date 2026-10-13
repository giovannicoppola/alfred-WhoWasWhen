package com.giovannicoppola.whowaswhen.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Article
import androidx.compose.material.icons.automirrored.filled.FormatListBulleted
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.giovannicoppola.whowaswhen.BuildConfig
import com.giovannicoppola.whowaswhen.model.SearchResult
import com.giovannicoppola.whowaswhen.model.formatYear
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min

/**
 * "Show all «title»" — the lineage of every holder of a title, with the
 * focused ruler highlighted. Offers two renderings of the same rows: the
 * classic list and a visual timeline.
 */
@Composable
fun LineageScreen(title: String, rulerID: Int?, prog: Int?, backLabel: String, onBack: () -> Unit) {
    val vm = LocalAppActions.current.vm
    var results by remember { mutableStateOf<List<SearchResult>>(emptyList()) }
    var loaded by remember { mutableStateOf(false) }
    // Automation hook (debug builds): open directly in timeline mode.
    var timeline by rememberSaveable { mutableStateOf(BuildConfig.DEBUG && DebugHooks.timeline) }

    LaunchedEffect(title, rulerID, prog) {
        results = vm.lineageResults(title, rulerID, prog)
        loaded = true
    }
    val focusedId = remember(results) { results.firstOrNull { it.isCurrent }?.id }

    IosScreen(
        navBar = {
            Row(
                Modifier.fillMaxWidth().height(44.dp).padding(horizontal = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IosBackButton(backLabel, onBack)
                Text(
                    title,
                    style = Ios.type.headline,
                    color = Ios.colors.label,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.weight(1f).padding(horizontal = 4.dp),
                )
                IosSegmentedControl(
                    count = 2,
                    selected = if (timeline) 1 else 0,
                    onSelect = { timeline = it == 1 },
                    modifier = Modifier.width(100.dp).padding(end = 8.dp),
                ) { i, _ ->
                    Icon(
                        if (i == 0) Icons.AutoMirrored.Filled.FormatListBulleted else Icons.AutoMirrored.Filled.Article,
                        contentDescription = if (i == 0) "List" else "Timeline",
                        tint = Ios.colors.label,
                        modifier = Modifier.size(18.dp),
                    )
                }
            }
        },
    ) {
        if (loaded) {
            if (timeline) {
                LineageTimeline(results = results, scrollToId = focusedId)
            } else {
                ResultsList(results = results, isIdle = false, scrollToId = focusedId)
            }
        } else {
            IosSpinner(Modifier.align(Alignment.Center))
        }
    }
}

private fun centuryStart(year: Int): Int = (floor(year / 100.0) * 100).toInt()

/**
 * A vertical timeline rendering of a title's lineage: one node per reign,
 * linked by a rail, with century markers where the era changes. The focused
 * ruler (🌟 in the list rendering) gets a highlighted node.
 */
@Composable
private fun LineageTimeline(results: List<SearchResult>, scrollToId: String?) {
    val listState = rememberLazyListState()

    // Lay out markers + entries as one flat list so item indices are known.
    val items = remember(results) {
        buildList {
            results.forEachIndexed { idx, result ->
                val marker = idx == 0 ||
                    centuryStart(result.startYear) != centuryStart(results[idx - 1].startYear)
                if (marker) add(TimelineItem.Marker(centuryStart(result.startYear), idx))
                add(TimelineItem.Entry(result, isFirst = idx == 0 && !marker, isLast = idx == results.size - 1))
            }
        }
    }
    CenterOnAppear(
        listState,
        scrollToId?.let { id -> items.indexOfFirst { it is TimelineItem.Entry && it.result.id == id }.takeIf { it >= 0 } },
    )

    LazyColumn(
        state = listState,
        modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 8.dp),
    ) {
        items.forEach { item ->
            when (item) {
                is TimelineItem.Marker -> item(key = "century-${item.index}") { CenturyMarker(item.year) }
                is TimelineItem.Entry -> item(key = item.result.id) {
                    TimelineEntry(item.result, item.isFirst, item.isLast)
                }
            }
        }
    }
}

private sealed interface TimelineItem {
    data class Marker(val year: Int, val index: Int) : TimelineItem
    data class Entry(val result: SearchResult, val isFirst: Boolean, val isLast: Boolean) : TimelineItem
}

/** The "1500 —" era divider on the timeline rail. */
@Composable
private fun CenturyMarker(year: Int) {
    Row(
        modifier = Modifier.padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text(
            formatYear(year),
            style = Ios.type.caption.copy(fontWeight = FontWeight.Bold).monospacedDigit(),
            color = Ios.colors.indigo,
            textAlign = TextAlign.End,
            modifier = Modifier.width(64.dp),
        )
        Box(
            modifier = Modifier
                .weight(1f)
                .height(1.dp)
                .background(Ios.colors.indigo.copy(alpha = 0.35f)),
        )
    }
}

/**
 * One reign on the timeline: rail + node on the left, tappable card on the
 * right. The node is scaled/filled for the focused ruler.
 */
@Composable
private fun TimelineEntry(result: SearchResult, isFirst: Boolean, isLast: Boolean) {
    val actions = LocalAppActions.current
    val c = Ios.colors
    val source = remember { MutableInteractionSource() }
    // Reign length in years, floored at 1 (single-year consulships).
    val reignLength = max(1, result.endYear - result.startYear)
    val yearLabel = if (result.startYear == result.endYear) formatYear(result.startYear)
    else "${formatYear(result.startYear)}–${formatYear(result.endYear)}"

    Row(
        modifier = Modifier
            .height(IntrinsicSize.Min)
            .clickable(interactionSource = source, indication = null) { actions.showDetail(result) },
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        // Years column.
        Text(
            yearLabel,
            style = Ios.type.caption2.copy(fontWeight = FontWeight.SemiBold).monospacedDigit(),
            color = c.secondaryLabel,
            textAlign = TextAlign.End,
            modifier = Modifier.width(64.dp).padding(top = 12.dp),
        )
        // Rail + node (fixed width so the rail stays straight past the
        // larger focused node).
        Column(
            modifier = Modifier.fillMaxHeight().width(19.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Box(
                Modifier.width(2.dp).height(14.dp)
                    .background(c.indigo.copy(alpha = if (isFirst) 0f else 0.3f)),
            )
            val nodeSize = if (result.isCurrent) 14.dp else 9.dp
            Box(contentAlignment = Alignment.Center) {
                if (result.isCurrent) {
                    // The soft halo around the focused ruler's node.
                    Box(Modifier.size(nodeSize + 5.dp).clip(CircleShape).background(c.yellow.copy(alpha = 0.35f)))
                }
                Box(
                    Modifier.size(nodeSize).clip(CircleShape)
                        .background(if (result.isCurrent) c.yellow else c.indigo),
                )
            }
            Box(
                Modifier.width(2.dp).weight(1f)
                    .background(c.indigo.copy(alpha = if (isLast) 0f else 0.3f)),
            )
        }
        // Card.
        Column(
            modifier = Modifier
                .weight(1f)
                .padding(vertical = 4.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(if (result.isCurrent) c.yellow.copy(alpha = 0.14f) else c.secondaryBackground)
                .rowHighlight(source)
                .padding(10.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                result.title,
                style = Ios.type.subheadline.copy(
                    fontWeight = if (result.isCurrent) FontWeight.Bold else FontWeight.Medium
                ),
                color = c.label,
            )
            if (result.subtitle.isNotEmpty()) {
                Text(
                    result.subtitle,
                    style = Ios.type.caption,
                    color = c.secondaryLabel,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            // Reign-length bar: longer reign, longer bar (capped at 60y).
            Box(
                modifier = Modifier
                    .height(4.dp)
                    .width((30 + 130 * min(reignLength, 60) / 60f).dp)
                    .clip(RoundedCornerShape(50))
                    .background(c.indigo.copy(alpha = 0.45f)),
            )
        }
    }
}

/**
 * A compact horizontal bar placing one reign inside the title's whole era —
 * shown in the detail sheet ("where in Pope history does this pope sit?").
 */
@Composable
fun ReignSpanBar(eraLabel: String, reignStart: Int, reignEnd: Int, era: IntRange) {
    val c = Ios.colors
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        BoxWithConstraints(Modifier.fillMaxWidth().height(8.dp)) {
            val track = c.secondaryLabel.copy(alpha = 0.18f)
            val fill = c.indigo
            Canvas(Modifier.fillMaxSize()) {
                val w = size.width
                val h = size.height
                val span = max(1, era.last - era.first)
                val x0 = (reignStart - era.first).toFloat() / span * w
                val x1 = (max(reignEnd, reignStart) - era.first).toFloat() / span * w
                val minW = 6.dp.toPx()
                // Keep even one-year reigns visible.
                val barW = max(minW, x1 - x0)
                val left = min(x0, w - minW)
                drawRoundRect(track, size = Size(w, h), cornerRadius = CornerRadius(h / 2))
                drawRoundRect(fill, topLeft = Offset(left, 0f), size = Size(barW, h), cornerRadius = CornerRadius(h / 2))
            }
        }
        Row(modifier = Modifier.fillMaxWidth()) {
            val style = Ios.type.caption2.monospacedDigit()
            Text(formatYear(era.first), style = style, color = c.secondaryLabel)
            Spacer(Modifier.weight(1f))
            Text(eraLabel, style = style, color = c.secondaryLabel)
            Spacer(Modifier.weight(1f))
            Text(formatYear(era.last), style = style, color = c.secondaryLabel)
        }
    }
}
