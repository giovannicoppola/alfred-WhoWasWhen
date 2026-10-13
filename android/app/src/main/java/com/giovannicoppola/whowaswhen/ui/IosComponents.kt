package com.giovannicoppola.whowaswhen.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.expandHorizontally
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkHorizontally
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Cancel
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.DpOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.cos
import kotlin.math.sin

// MARK: - Press feedback

/** iOS-style tap: no ripple, just a brief dim of the content while pressed. */
@Composable
fun Modifier.iosClickable(enabled: Boolean = true, onClick: () -> Unit): Modifier {
    val source = remember { MutableInteractionSource() }
    val pressed by source.collectIsPressedAsState()
    val alpha by animateFloatAsState(if (pressed) 0.35f else 1f, tween(if (pressed) 0 else 180), label = "press")
    return this
        .clickable(interactionSource = source, indication = null, enabled = enabled, onClick = onClick)
        .alpha(alpha)
}

/** A list row's gray highlight while pressed (UITableViewCell selection). */
@Composable
fun Modifier.rowHighlight(source: MutableInteractionSource): Modifier {
    val pressed by source.collectIsPressedAsState()
    val c = Ios.colors
    val color by animateColorAsState(
        if (pressed) (if (c.isDark) Color(0xFF3A3A3C) else Color(0xFFD1D1D6)) else Color.Transparent,
        tween(if (pressed) 0 else 250), label = "rowHighlight",
    )
    return this.background(color)
}

// MARK: - Navigation bar

/** The inline navigation bar: centered 17pt semibold title, leading/trailing items. */
@Composable
fun IosNavBar(
    title: String,
    background: Color = Ios.colors.background,
    leading: (@Composable RowScope.() -> Unit)? = null,
    trailing: (@Composable RowScope.() -> Unit)? = null,
    titleInset: Dp = 96.dp,
    /** Replaces the title (`ToolbarItem(placement: .principal)`). */
    center: (@Composable () -> Unit)? = null,
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(background)
            .height(44.dp)
            .padding(horizontal = 8.dp),
    ) {
        if (center != null) {
            Box(Modifier.align(Alignment.Center)) { center() }
        } else {
            Text(
                title,
                style = Ios.type.headline,
                color = Ios.colors.label,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                textAlign = TextAlign.Center,
                modifier = Modifier.align(Alignment.Center).padding(horizontal = titleInset),
            )
        }
        if (leading != null) {
            Row(Modifier.align(Alignment.CenterStart), verticalAlignment = Alignment.CenterVertically, content = leading)
        }
        if (trailing != null) {
            Row(Modifier.align(Alignment.CenterEnd), verticalAlignment = Alignment.CenterVertically, content = trailing)
        }
    }
}

/** "‹ WhoWasWhen" — the back button, labelled with the previous screen's title. */
@Composable
fun IosBackButton(label: String, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .iosClickable(onClick = onClick)
            .padding(end = 8.dp)
            .height(44.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(SfIcons.ChevronLeft, "Back", tint = Ios.colors.accent, modifier = Modifier.size(22.dp))
        Spacer(Modifier.width(4.dp))
        Text(label, style = Ios.type.body, color = Ios.colors.accent, maxLines = 1)
    }
}

/** A plain text bar button ("Done", "End"). */
@Composable
fun IosBarButton(text: String, bold: Boolean = false, onClick: () -> Unit) {
    Text(
        text,
        style = Ios.type.body.copy(fontWeight = if (bold) FontWeight.SemiBold else FontWeight.Normal),
        color = Ios.colors.accent,
        modifier = Modifier
            .iosClickable(onClick = onClick)
            .padding(horizontal = 8.dp, vertical = 10.dp),
    )
}

// MARK: - Tab bar

data class IosTab(val label: String, val icon: ImageVector)

/** The bottom tab bar: hairline top edge, translucent chrome, accent selection. */
@Composable
fun IosTabBar(tabs: List<IosTab>, selected: Int, onSelect: (Int) -> Unit) {
    val c = Ios.colors
    Column(Modifier.fillMaxWidth().background(c.chrome)) {
        Box(Modifier.fillMaxWidth().height(0.5.dp).background(c.separator))
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .height(50.dp),
        ) {
            tabs.forEachIndexed { i, tab ->
                val tint = if (i == selected) c.accent else c.gray
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxHeight()
                        .clickable(
                            interactionSource = remember { MutableInteractionSource() },
                            indication = null,
                        ) { onSelect(i) }
                        .padding(top = 5.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Icon(tab.icon, tab.label, tint = tint, modifier = Modifier.size(26.dp))
                    Spacer(Modifier.height(2.dp))
                    Text(tab.label, style = Ios.type.tabLabel, color = tint)
                }
            }
        }
    }
}

// MARK: - Search field

/**
 * The navigation-bar search field: gray rounded field with a magnifier and a
 * clear button, plus a "Cancel" button while searching is active.
 */
@Composable
fun IosSearchField(
    query: String,
    onQueryChange: (String) -> Unit,
    placeholder: String,
    active: Boolean,
    onActivate: () -> Unit,
    onCancel: () -> Unit,
    onSubmit: () -> Unit,
    focusRequester: FocusRequester,
) {
    val c = Ios.colors
    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(
            modifier = Modifier
                .weight(1f)
                .height(36.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(c.fill)
                .padding(horizontal = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(Icons.Filled.Search, null, tint = c.secondaryLabel, modifier = Modifier.size(22.dp))
            Spacer(Modifier.width(4.dp))
            Box(Modifier.weight(1f), contentAlignment = Alignment.CenterStart) {
                if (query.isEmpty()) {
                    Text(placeholder, style = Ios.type.body, color = c.secondaryLabel, maxLines = 1)
                }
                BasicTextField(
                    value = query,
                    onValueChange = onQueryChange,
                    singleLine = true,
                    textStyle = Ios.type.body.copy(color = c.label),
                    cursorBrush = SolidColor(c.accent),
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                    keyboardActions = KeyboardActions(onSearch = { onSubmit() }),
                    modifier = Modifier
                        .fillMaxWidth()
                        .focusRequester(focusRequester)
                        .onFocusChanged { if (it.isFocused) onActivate() },
                )
            }
            if (query.isNotEmpty()) {
                Icon(
                    Icons.Filled.Cancel, "Clear", tint = c.secondaryLabel,
                    modifier = Modifier
                        .size(26.dp)
                        .clickable(
                            interactionSource = remember { MutableInteractionSource() },
                            indication = null,
                        ) { onQueryChange("") }
                        .padding(4.dp),
                )
            }
        }
        AnimatedVisibility(
            visible = active,
            enter = expandHorizontally() + fadeIn(),
            exit = shrinkHorizontally() + fadeOut(),
        ) {
            Text(
                "Cancel",
                style = Ios.type.body,
                color = c.accent,
                modifier = Modifier.iosClickable(onClick = onCancel).padding(start = 12.dp, top = 8.dp, bottom = 8.dp),
            )
        }
    }
}

// MARK: - Segmented control

/** UISegmentedControl: gray track, raised white thumb, equal-width segments. */
@Composable
fun IosSegmentedControl(
    count: Int,
    selected: Int,
    onSelect: (Int) -> Unit,
    modifier: Modifier = Modifier,
    segment: @Composable (index: Int, isSelected: Boolean) -> Unit,
) {
    val c = Ios.colors
    BoxWithConstraints(
        modifier = modifier
            .height(32.dp)
            .clip(RoundedCornerShape(9.dp))
            .background(c.fill)
            .padding(2.dp),
    ) {
        val segWidth = maxWidth / count
        val thumbX by androidx.compose.animation.core.animateDpAsState(segWidth * selected, label = "thumb")
        Box(
            Modifier
                .offset(x = thumbX)
                .width(segWidth)
                .fillMaxHeight()
                .shadow(2.dp, RoundedCornerShape(7.dp))
                .clip(RoundedCornerShape(7.dp))
                .background(c.segmentThumb),
        )
        Row(Modifier.fillMaxSize()) {
            for (i in 0 until count) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxHeight()
                        .clickable(
                            interactionSource = remember { MutableInteractionSource() },
                            indication = null,
                        ) { onSelect(i) },
                    contentAlignment = Alignment.Center,
                ) { segment(i, i == selected) }
                if (i < count - 1) {
                    val hidden = i == selected || i + 1 == selected
                    Box(
                        Modifier
                            .padding(vertical = 7.dp)
                            .width(1.dp)
                            .fillMaxHeight()
                            .background(if (hidden) Color.Transparent else c.separator)
                    )
                }
            }
        }
    }
}

/** Convenience for text segments ("All / People / Events"). */
@Composable
fun IosTextSegments(
    labels: List<String>,
    selected: Int,
    onSelect: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    IosSegmentedControl(labels.size, selected, onSelect, modifier) { i, isSel ->
        Text(
            labels[i],
            style = Ios.type.footnote.copy(
                fontWeight = if (isSel) FontWeight.SemiBold else FontWeight.Medium,
                fontSize = 13.sp,
            ),
            color = Ios.colors.label,
            maxLines = 1,
        )
    }
}

// MARK: - Grouped lists (insetGrouped)

/** A grouped-list section header: uppercase footnote in secondary gray. */
@Composable
fun GroupedHeader(text: String, modifier: Modifier = Modifier) {
    Text(
        text.uppercase(),
        style = Ios.type.footnote,
        color = Ios.colors.secondaryLabel,
        modifier = modifier.padding(start = 36.dp, end = 36.dp, top = 22.dp, bottom = 7.dp),
    )
}

/** A grouped-list section body: an inset rounded card. */
@Composable
fun GroupedCard(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Column(
        modifier = modifier
            .padding(horizontal = 16.dp)
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(Ios.colors.groupedCell),
        content = content,
    )
}

/** A hairline row separator, inset from the leading edge like UITableView. */
@Composable
fun IosDivider(startInset: Dp = 16.dp) {
    Box(
        Modifier
            .padding(start = startInset)
            .fillMaxWidth()
            .height(0.5.dp)
            .background(Ios.colors.separator)
    )
}

/**
 * A tappable grouped-list action row: accent icon + accent label, as in the
 * detail sheet's Actions section.
 */
@Composable
fun GroupedActionRow(icon: ImageVector, label: String, onClick: () -> Unit) {
    val source = remember { MutableInteractionSource() }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .rowHighlight(source)
            .clickable(interactionSource = source, indication = null, onClick = onClick)
            .heightIn(min = 44.dp)
            .padding(horizontal = 20.dp, vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, null, tint = Ios.colors.accent, modifier = Modifier.size(22.dp))
        Spacer(Modifier.width(18.dp))
        Text(label, style = Ios.type.body, color = Ios.colors.accent)
    }
}

// MARK: - Buttons

enum class IosButtonStyle { PROMINENT, BORDERED }

/**
 * `.borderedProminent` / `.bordered` buttons. [tint] colors the fill
 * (prominent) or the label + translucent fill (bordered); null = gray fill.
 */
@Composable
fun IosButton(
    text: String,
    style: IosButtonStyle,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    tint: Color? = null,
    capsule: Boolean = false,
    small: Boolean = false,
    icon: ImageVector? = null,
    fillWidth: Boolean = false,
) {
    val c = Ios.colors
    val accent = tint ?: c.accent
    val (bg, fg) = when (style) {
        IosButtonStyle.PROMINENT -> accent to Color.White
        IosButtonStyle.BORDERED ->
            (if (tint == null) c.fill else accent.copy(alpha = 0.15f)) to accent
    }
    val shape = if (capsule) RoundedCornerShape(50) else RoundedCornerShape(if (small) 7.dp else 10.dp)
    val textStyle = if (small) Ios.type.footnote.copy(fontWeight = FontWeight.SemiBold) else Ios.type.body
    Row(
        modifier = modifier
            .clip(shape)
            .background(bg)
            .iosClickable(onClick = onClick)
            .then(if (fillWidth) Modifier.fillMaxWidth() else Modifier)
            .padding(
                horizontal = if (small) 11.dp else 14.dp,
                vertical = if (small) 5.dp else 8.dp,
            ),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) {
            Icon(icon, null, tint = fg, modifier = Modifier.size(if (small) 15.dp else 18.dp))
            Spacer(Modifier.width(6.dp))
        }
        Text(text, style = textStyle, color = fg)
    }
}

// MARK: - Progress

/** The iOS activity indicator: eight fading spokes stepping around. */
@Composable
fun IosSpinner(modifier: Modifier = Modifier, size: Dp = 26.dp) {
    val c = Ios.colors
    val transition = rememberInfiniteTransition(label = "spinner")
    val phase by transition.animateFloat(
        0f, 8f, infiniteRepeatable(tween(800, easing = LinearEasing)), label = "phase",
    )
    Canvas(modifier.size(size)) {
        val step = phase.toInt()
        val r = this.size.minDimension / 2
        for (i in 0 until 8) {
            val a = Math.toRadians(i * 45.0 - 90.0)
            val dir = Offset(cos(a).toFloat(), sin(a).toFloat())
            val alpha = 1f - (((step - i) % 8 + 8) % 8) / 8f * 0.85f
            drawLine(
                c.gray.copy(alpha = alpha),
                center + dir * (r * 0.45f),
                center + dir * (r * 0.95f),
                strokeWidth = r * 0.2f,
                cap = StrokeCap.Round,
            )
        }
    }
}

/** A spinner with a caption beneath ("Preparing questions…"). */
@Composable
fun IosProgressView(label: String? = null) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        IosSpinner()
        if (label != null) {
            Spacer(Modifier.height(8.dp))
            Text(label, style = Ios.type.body, color = Ios.colors.secondaryLabel)
        }
    }
}

/** A linear ProgressView: thin gray track with a tinted fill. */
@Composable
fun IosProgressBar(progress: Float, tint: Color, modifier: Modifier = Modifier) {
    val animated by animateFloatAsState(progress.coerceIn(0f, 1f), label = "progress")
    Box(
        modifier
            .fillMaxWidth()
            .height(4.dp)
            .clip(RoundedCornerShape(2.dp))
            .background(Ios.colors.fill)
    ) {
        Box(
            Modifier
                .fillMaxWidth(animated)
                .fillMaxHeight()
                .clip(RoundedCornerShape(2.dp))
                .background(tint)
        )
    }
}

// MARK: - Empty states

/** ContentUnavailableView: large gray symbol, bold title, secondary description. */
@Composable
fun ContentUnavailable(icon: ImageVector, title: String, description: String?) {
    Column(
        modifier = Modifier.fillMaxSize().padding(horizontal = 40.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(icon, null, tint = Ios.colors.secondaryLabel, modifier = Modifier.size(52.dp))
        Spacer(Modifier.height(14.dp))
        Text(title, style = Ios.type.title2, color = Ios.colors.label, textAlign = TextAlign.Center)
        if (description != null) {
            Spacer(Modifier.height(8.dp))
            Text(
                description,
                style = Ios.type.subheadline,
                color = Ios.colors.secondaryLabel,
                textAlign = TextAlign.Center,
            )
        }
    }
}

// MARK: - Toast

/** The self-dismissing confirmation capsule ("Copied to clipboard"). */
@Composable
fun ToastBanner(text: String, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier
            .shadow(6.dp, CircleShape)
            .clip(CircleShape)
            .background(Color.Black.copy(alpha = 0.8f))
            .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Filled.CheckCircle, null, tint = Color.White, modifier = Modifier.size(18.dp))
        Spacer(Modifier.width(8.dp))
        Text(text, style = Ios.type.subheadline.copy(fontWeight = FontWeight.SemiBold), color = Color.White)
    }
}

/**
 * Overlays [ToastBanner] at the bottom of a layer, springing in from below.
 * [modifier] sizes the layer (fillMaxSize / matchParentSize).
 */
@Composable
fun ToastHost(message: String?, modifier: Modifier, bottomPadding: Dp = 32.dp) {
    Box(modifier, contentAlignment = Alignment.BottomCenter) {
        var last by remember { mutableStateOf("") }
        if (message != null) last = message
        AnimatedVisibility(
            visible = message != null,
            enter = androidx.compose.animation.slideInVertically { it } + fadeIn(),
            exit = androidx.compose.animation.slideOutVertically { it } + fadeOut(),
            modifier = Modifier.padding(bottom = bottomPadding),
        ) { ToastBanner(last) }
    }
}

// MARK: - Menus (context menu / pull-down)

/**
 * An iOS-style context/pull-down menu: rounded translucent panel, full-width
 * rows with the label leading and the symbol trailing.
 */
@Composable
fun IosMenu(
    expanded: Boolean,
    onDismiss: () -> Unit,
    offset: DpOffset = DpOffset(0.dp, 0.dp),
    content: @Composable ColumnScope.() -> Unit,
) {
    val c = Ios.colors
    DropdownMenu(
        expanded = expanded,
        onDismissRequest = onDismiss,
        offset = offset,
        shape = RoundedCornerShape(13.dp),
        containerColor = if (c.isDark) Color(0xFF2C2C2E) else Color(0xFFF2F2F2),
        tonalElevation = 0.dp,
        shadowElevation = 12.dp,
        modifier = Modifier.widthIn(min = 250.dp),
        content = content,
    )
}

@Composable
fun IosMenuItem(
    text: String,
    icon: ImageVector?,
    onClick: () -> Unit,
    showDivider: Boolean = true,
    trailingRotation: Float = 0f,
    indent: Dp = 0.dp,
) {
    val source = remember { MutableInteractionSource() }
    Column {
        Row(
            modifier = Modifier
                .widthIn(min = 250.dp)
                .rowHighlight(source)
                .clickable(interactionSource = source, indication = null, onClick = onClick)
                .padding(start = 16.dp + indent, end = 16.dp, top = 11.dp, bottom = 11.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(text, style = Ios.type.body, color = Ios.colors.label, modifier = Modifier.weight(1f))
            if (icon != null) {
                Spacer(Modifier.width(16.dp))
                Icon(
                    icon, null, tint = Ios.colors.label,
                    modifier = Modifier.size(20.dp).rotate(trailingRotation),
                )
            }
        }
        if (showDivider) Box(Modifier.fillMaxWidth().height(0.5.dp).background(Ios.colors.separator))
    }
}

/** Small padding helper used by grouped rows. */
val GroupedRowPadding = PaddingValues(horizontal = 20.dp, vertical = 11.dp)

/** A 1pt stroke rounded border, as on the quiz option buttons. */
fun Modifier.hairlineBorder(color: Color, radius: Dp) =
    this.border(1.dp, color, RoundedCornerShape(radius))
