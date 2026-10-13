package com.giovannicoppola.whowaswhen.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.FormatListBulleted
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.outlined.AccountCircle
import androidx.compose.material.icons.outlined.ContentCopy
import androidx.compose.material.icons.outlined.Explore
import androidx.compose.material.icons.outlined.Flag
import androidx.compose.material.icons.outlined.StarOutline
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.giovannicoppola.whowaswhen.data.WikipediaClient
import com.giovannicoppola.whowaswhen.model.ResultKind
import com.giovannicoppola.whowaswhen.model.SearchResult
import com.giovannicoppola.whowaswhen.model.formatYear
import com.giovannicoppola.whowaswhen.model.titlePluralOrDefault

/** "Lived 1491–1547 (aged 56)" — or the born/died half that is known. */
private fun lifespanLine(result: SearchResult): String? {
    if (result.kind != ResultKind.RULER) return null
    val born = result.born
    val died = result.died
    return when {
        born != null && died != null -> "Lived ${formatYear(born)}–${formatYear(died)} (aged ${died - born})"
        born != null -> "Born ${formatYear(born)}"
        died != null -> "Died ${formatYear(died)}"
        else -> null
    }
}

/**
 * Detail sheet shown when a result is tapped: full text plus every action,
 * laid out as the iOS inset-grouped list. Navigation actions dismiss the
 * sheet first. Mirrors iOS ResultDetailView.
 */
@Composable
fun ResultDetailContent(result: SearchResult) {
    val actions = LocalAppActions.current
    val vm = actions.vm
    val c = Ios.colors
    val favorites by vm.favorites.entries.collectAsStateWithLifecycle()
    val isFavorite = remember(favorites, result) { vm.favorites.isFavorite(result) }

    // The full span of the ruler's title, for the mini reign-position bar.
    var eraSpan by remember(result.id) { mutableStateOf<IntRange?>(null) }
    // First-paragraph summary fetched from Wikipedia (null offline).
    var extract by remember(result.id) { mutableStateOf<String?>(null) }
    var reportOpen by remember { mutableStateOf(false) }

    LaunchedEffect(result.id) {
        if (result.kind == ResultKind.RULER && result.titleName != null) {
            eraSpan = vm.titleSpan(result.titleName!!)
        }
        result.wikipediaUrl?.let { extract = WikipediaClient.summary(it)?.extract }
    }

    val dismiss = LocalDismissSheet.current
    fun dismissThen(block: () -> Unit) {
        dismiss()
        block()
    }

    Box {
        Column(Modifier.fillMaxWidth().background(c.groupedBackground)) {
            IosNavBar(
                title = "Details",
                background = c.groupedBackground,
                leading = {
                    // The filled/empty star mirrors the saved state directly.
                    Icon(
                        if (isFavorite) Icons.Filled.Star else Icons.Outlined.StarOutline,
                        contentDescription = if (isFavorite) "Remove from Favorites" else "Add to Favorites",
                        tint = c.yellow,
                        modifier = Modifier
                            .iosClickable { vm.toggleFavorite(result) }
                            .padding(8.dp)
                            .size(26.dp),
                    )
                },
                trailing = { IosBarButton("Done") { dismiss() } },
            )
            Column(
                Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
            ) {
                Spacer(Modifier.height(18.dp))
                GroupedCard {
                    Row(
                        modifier = Modifier.padding(horizontal = 20.dp, vertical = 14.dp),
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        PortraitView(result = result, size = 64.dp)
                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(result.title, style = Ios.type.headline, color = c.label)
                            result.personalName?.takeIf { it.isNotEmpty() }?.let {
                                Text(it, style = Ios.type.subheadline.copy(fontStyle = FontStyle.Italic), color = c.secondaryLabel)
                            }
                            if (result.subtitle.isNotEmpty()) {
                                Text(result.subtitle, style = Ios.type.subheadline, color = c.secondaryLabel)
                            }
                            lifespanLine(result)?.let {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(Icons.Outlined.AccountCircle, null, tint = c.secondaryLabel, modifier = Modifier.size(18.dp))
                                    Spacer(Modifier.width(8.dp))
                                    Text(it, style = Ios.type.footnote, color = c.secondaryLabel)
                                }
                            }
                        }
                    }
                    // Where this reign sits within the title's whole history.
                    val span = eraSpan
                    val title = result.titleName
                    if (span != null && title != null) {
                        IosDivider(startInset = 96.dp)
                        Box(Modifier.padding(horizontal = 20.dp, vertical = 14.dp)) {
                            ReignSpanBar(
                                eraLabel = "all ${titlePluralOrDefault(result.titlePlural, title)}",
                                reignStart = result.startYear,
                                reignEnd = result.endYear,
                                era = span,
                            )
                        }
                    }
                }

                extract?.let {
                    GroupedHeader("About")
                    GroupedCard {
                        Column(
                            Modifier.padding(horizontal = 20.dp, vertical = 13.dp),
                            verticalArrangement = Arrangement.spacedBy(6.dp),
                        ) {
                            Text(it, style = Ios.type.subheadline, color = c.label)
                            Text("From Wikipedia", style = Ios.type.caption2, color = c.tertiaryLabel)
                        }
                    }
                }

                GroupedHeader("Actions")
                GroupedCard {
                    // The list of rulers (lineage) is the primary action, so it comes first.
                    if (result.kind == ResultKind.RULER && !result.titleName.isNullOrEmpty()) {
                        val t = result.titleName!!
                        GroupedActionRow(
                            Icons.AutoMirrored.Filled.FormatListBulleted,
                            "Show all ${titlePluralOrDefault(result.titlePlural, t)}",
                        ) { dismissThen { actions.showLineage(result) } }
                        IosDivider(startInset = 60.dp)
                    }
                    GroupedActionRow(SfIcons.ArrowBackwardToLine, "Travel to ${formatYear(result.startYear)}") {
                        dismissThen { actions.travel(result.startYear) }
                    }
                    IosDivider(startInset = 60.dp)
                    if (result.endYear != result.startYear) {
                        GroupedActionRow(SfIcons.ArrowForwardToLine, "Travel to ${formatYear(result.endYear)}") {
                            dismissThen { actions.travel(result.endYear) }
                        }
                        IosDivider(startInset = 60.dp)
                    }
                    GroupedActionRow(Icons.Outlined.ContentCopy, "Copy to clipboard") { actions.copy(result) }
                    // Wikipedia link last.
                    result.wikipediaUrl?.let { url ->
                        IosDivider(startInset = 60.dp)
                        GroupedActionRow(Icons.Outlined.Explore, "Open Wikipedia") { actions.openUrl(url) }
                    }
                    IosDivider(startInset = 60.dp)
                    Box {
                        GroupedActionRow(Icons.Outlined.Flag, "Report an issue") { reportOpen = true }
                        Box(Modifier.align(Alignment.TopEnd).padding(end = 16.dp)) {
                            IosMenu(expanded = reportOpen, onDismiss = { reportOpen = false }) {
                                ReportMenuItems(result, open = true, onToggle = {}, onDone = { reportOpen = false }, showHeader = false)
                            }
                        }
                    }
                }
                Spacer(Modifier.height(32.dp))
            }
        }
        // Applied inside this presentation layer so the banner renders in
        // front of the sheet rather than behind it.
        // matchParentSize: cover the sheet without forcing it to full height.
        ToastHost(vm.toast, Modifier.matchParentSize())
    }
}
