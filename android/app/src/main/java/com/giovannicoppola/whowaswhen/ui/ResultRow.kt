package com.giovannicoppola.whowaswhen.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.FormatListBulleted
import androidx.compose.material.icons.outlined.BugReport
import androidx.compose.material.icons.outlined.ChevronRight
import androidx.compose.material.icons.outlined.ContentCopy
import androidx.compose.material.icons.outlined.Email
import androidx.compose.material.icons.outlined.Explore
import androidx.compose.material.icons.outlined.Flag
import androidx.compose.material.icons.outlined.StarOutline
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.giovannicoppola.whowaswhen.model.ResultKind
import com.giovannicoppola.whowaswhen.model.SearchResult
import com.giovannicoppola.whowaswhen.model.formatNumber
import com.giovannicoppola.whowaswhen.model.formatYear
import com.giovannicoppola.whowaswhen.model.titlePluralOrDefault

/**
 * One result row with the workflow's full action set exposed via swipe
 * gestures, a long-press context menu, and (on tap) the detail sheet.
 * The position badge ("3/11") is hidden for single highlights.
 */
@Composable
fun ResultRow(
    result: SearchResult,
    index: Int,
    total: Int,
    showCounter: Boolean = true,
    background: Color = Ios.colors.background,
) {
    ResultActionsContainer(result, background) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 11.dp),
            verticalAlignment = Alignment.Top,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // Icon + result-position counter. The counter is a distinct,
            // monospaced badge so it reads as "where you are in the results"
            // rather than data about the ruler.
            Column(
                modifier = Modifier.width(52.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                PortraitView(result = result, size = 36.dp)
                if (showCounter) {
                    Text(
                        text = "${formatNumber(index + 1)}/${formatNumber(total)}",
                        style = Ios.type.caption2.copy(fontWeight = FontWeight.SemiBold).monospacedDigit(),
                        color = Ios.colors.secondaryLabel,
                        maxLines = 1,
                        softWrap = false,
                        modifier = Modifier
                            .background(Ios.colors.secondaryFill, RoundedCornerShape(50))
                            .padding(horizontal = 5.dp, vertical = 1.dp),
                    )
                }
            }
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(
                    text = result.title,
                    style = Ios.type.body.copy(
                        fontWeight = if (result.isCurrent) FontWeight.Bold else FontWeight.Normal
                    ),
                    color = Ios.colors.label,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                result.personalName?.takeIf { it.isNotEmpty() }?.let {
                    Text(
                        text = it,
                        style = Ios.type.caption.copy(fontStyle = FontStyle.Italic),
                        color = Ios.colors.secondaryLabel,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                if (result.subtitle.isNotEmpty()) {
                    Text(
                        text = result.subtitle,
                        style = Ios.type.caption,
                        color = Ios.colors.secondaryLabel,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}

/**
 * The swipe gestures + long-press context menu + tap-for-details every
 * result-style row shares — used by [ResultRow] and the Discover tab's
 * featured cards (the iOS `resultRowActions(for:)` modifier).
 */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun ResultActionsContainer(
    result: SearchResult,
    background: Color,
    content: @Composable () -> Unit,
) {
    val actions = LocalAppActions.current
    val c = Ios.colors
    val favorites by actions.vm.favorites.entries.collectAsStateWithLifecycle()
    val saved = remember(favorites, result) { actions.vm.favorites.isFavorite(result) }
    var menuOpen by remember { mutableStateOf(false) }
    val source = remember { MutableInteractionSource() }

    // Single-year results get one travel button, not a duplicated
    // Start/End pair pointing at the same year. Just the year as the label —
    // the back/forward icons and tints already convey start vs end.
    val leading = if (result.startYear == result.endYear) {
        listOf(SwipeAction(formatYear(result.startYear), SfIcons.ArrowForwardToLine, c.blue) {
            actions.travel(result.startYear)
        })
    } else {
        listOf(
            SwipeAction(formatYear(result.startYear), SfIcons.ArrowBackwardToLine, c.blue) {
                actions.travel(result.startYear)
            },
            SwipeAction(formatYear(result.endYear), SfIcons.ArrowForwardToLine, c.teal) {
                actions.travel(result.endYear)
            },
        )
    }
    val trailing = buildList {
        add(SwipeAction(
            if (saved) "Remove Favorite" else "Add to Favorites",
            if (saved) SfIcons.StarSlash else Icons.Outlined.StarOutline,
            c.yellow, width = 96.dp,
        ) { actions.toggleFavorite(result) })
        result.wikipediaUrl?.let { url ->
            add(SwipeAction("Wikipedia", Icons.Outlined.Explore, c.indigo, width = 84.dp) { actions.openUrl(url) })
        }
        if (result.kind == ResultKind.RULER && !result.titleName.isNullOrEmpty()) {
            add(SwipeAction("All", Icons.AutoMirrored.Filled.FormatListBulleted, c.purple) {
                actions.showLineage(result)
            })
        }
    }

    SwipeActionsBox(key = result.id, leading = leading, trailing = trailing, background = background) {
        Box(
            Modifier
                .rowHighlight(source)
                .combinedClickable(
                    interactionSource = source,
                    indication = null,
                    onClick = { actions.showDetail(result) },
                    onLongClick = { actions.hapticLongPress(); menuOpen = true },
                )
        ) {
            content()
            Box(Modifier.align(Alignment.TopStart).padding(start = 24.dp)) {
                ResultContextMenu(result, expanded = menuOpen, onDismiss = { menuOpen = false })
            }
        }
    }
}

/**
 * The long-press context menu: the full iOS `ResultActions` set (show
 * lineage, travel, copy, favorite, Wikipedia, report).
 */
@Composable
fun ResultContextMenu(result: SearchResult, expanded: Boolean, onDismiss: () -> Unit) {
    val actions = LocalAppActions.current
    val favorites by actions.vm.favorites.entries.collectAsStateWithLifecycle()
    val saved = remember(favorites, result) { actions.vm.favorites.isFavorite(result) }
    var reportOpen by remember(expanded) { mutableStateOf(false) }

    fun run(block: () -> Unit) { onDismiss(); block() }

    IosMenu(expanded = expanded, onDismiss = onDismiss) {
        if (result.kind == ResultKind.RULER && !result.titleName.isNullOrEmpty()) {
            IosMenuItem(
                "Show all ${titlePluralOrDefault(result.titlePlural, result.titleName!!)}",
                Icons.AutoMirrored.Filled.FormatListBulleted,
                { run { actions.showLineage(result) } },
            )
        }
        IosMenuItem("Travel to ${formatYear(result.startYear)}", SfIcons.ArrowBackwardToLine,
            { run { actions.travel(result.startYear) } })
        if (result.endYear != result.startYear) {
            IosMenuItem("Travel to ${formatYear(result.endYear)}", SfIcons.ArrowForwardToLine,
                { run { actions.travel(result.endYear) } })
        }
        IosMenuItem("Copy", Icons.Outlined.ContentCopy, { run { actions.copy(result) } })
        IosMenuItem(
            if (saved) "Remove Favorite" else "Add to Favorites",
            if (saved) SfIcons.StarSlash else Icons.Outlined.StarOutline,
            { run { actions.toggleFavorite(result) } },
        )
        result.wikipediaUrl?.let { url ->
            IosMenuItem("Open Wikipedia", Icons.Outlined.Explore, { run { actions.openUrl(url) } })
        }
        ReportMenuItems(result, reportOpen, onToggle = { reportOpen = !reportOpen }, onDone = onDismiss)
    }
}

/**
 * The "Report an issue" submenu (By email / On GitHub), expanding in place
 * like an iOS inline submenu.
 */
@Composable
fun ReportMenuItems(
    result: SearchResult?,
    open: Boolean,
    onToggle: () -> Unit,
    onDone: () -> Unit,
    label: String = "Report an issue",
    showHeader: Boolean = true,
) {
    val actions = LocalAppActions.current
    if (showHeader) {
        IosMenuItem(
            label, if (open) Icons.Outlined.ChevronRight else Icons.Outlined.Flag, onToggle,
            showDivider = open, trailingRotation = if (open) 90f else 0f,
        )
    }
    if (open || !showHeader) {
        IosMenuItem("By email", Icons.Outlined.Email, {
            onDone(); actions.openUrl(Reporting.emailUrl(result))
        }, indent = if (showHeader) 12.dp else 0.dp)
        IosMenuItem("On GitHub", Icons.Outlined.BugReport, {
            onDone(); actions.openUrl(Reporting.githubUrl(result))
        }, showDivider = false, indent = if (showHeader) 12.dp else 0.dp)
    }
}
