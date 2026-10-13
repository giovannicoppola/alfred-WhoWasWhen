package com.giovannicoppola.whowaswhen.ui

import androidx.compose.animation.core.animate
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.Orientation
import androidx.compose.foundation.gestures.draggable
import androidx.compose.foundation.gestures.rememberDraggableState
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlin.math.abs
import kotlin.math.roundToInt

/** One swipe button: a full-height colored slab with a white symbol + label. */
data class SwipeAction(
    val label: String,
    val icon: ImageVector,
    val color: Color,
    val width: Dp = 76.dp,
    val onClick: () -> Unit,
)

/** Ensures only one row in a list has its swipe actions open at a time. */
@Stable
class SwipeCoordinator {
    var openKey by mutableStateOf<Any?>(null)
}

val LocalSwipeCoordinator = compositionLocalOf { SwipeCoordinator() }

/**
 * `.swipeActions(edge:allowsFullSwipe: false)` for Compose: drag the row right
 * to reveal [leading] actions, left to reveal [trailing] ones (both listed
 * from the row's edge inward, as in SwiftUI). Releasing past
 * half of the button width snaps open; tapping the row or another row closes.
 */
@Composable
fun SwipeActionsBox(
    key: Any,
    leading: List<SwipeAction>,
    trailing: List<SwipeAction>,
    background: Color,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    val coordinator = LocalSwipeCoordinator.current
    val density = LocalDensity.current
    val scope = rememberCoroutineScope()
    val maxRight = with(density) { leading.sumOf { it.width.value.toDouble() }.toFloat().dp.toPx() }
    val maxLeft = -with(density) { trailing.sumOf { it.width.value.toDouble() }.toFloat().dp.toPx() }
    // The row's horizontal offset. Drag deltas apply synchronously (so the
    // release position is exact); only the settle is animated.
    var offset by remember { mutableFloatStateOf(0f) }
    var settleJob by remember { mutableStateOf<Job?>(null) }

    fun animateTo(target: Float) {
        settleJob?.cancel()
        settleJob = scope.launch {
            animate(offset, target, animationSpec = spring(dampingRatio = 0.85f, stiffness = Spring.StiffnessMediumLow)) { v, _ ->
                offset = v
            }
        }
    }

    fun settle(target: Float) {
        animateTo(target)
        if (target != 0f) coordinator.openKey = key
        else if (coordinator.openKey == key) coordinator.openKey = null
    }

    // Another row opened (or the list scrolled): close this one.
    LaunchedEffect(coordinator.openKey) {
        if (coordinator.openKey != key && offset != 0f) animateTo(0f)
    }

    val dragState = rememberDraggableState { delta ->
        settleJob?.cancel()
        // Rubber-band a little past the fully open position.
        val raw = offset + delta
        offset = when {
            raw > maxRight -> maxRight + (raw - maxRight) * 0.3f
            raw < maxLeft -> maxLeft + (raw - maxLeft) * 0.3f
            else -> raw
        }
    }

    Box(modifier) {
        // Revealed buttons behind the row.
        Row(Modifier.matchParentSize()) {
            val revealRight = offset.coerceAtLeast(0f)
            val revealLeft = (-offset).coerceAtLeast(0f)
            if (revealRight > 0f && leading.isNotEmpty()) {
                ActionStrip(leading, with(density) { revealRight.toDp() }) { action ->
                    settle(0f); action.onClick()
                }
            }
            Spacer(Modifier.weight(1f))
            if (revealLeft > 0f && trailing.isNotEmpty()) {
                ActionStrip(trailing.reversed(), with(density) { revealLeft.toDp() }) { action ->
                    settle(0f); action.onClick()
                }
            }
        }
        Box(
            Modifier
                .offset { IntOffset(offset.roundToInt(), 0) }
                .background(background)
                .draggable(
                    state = dragState,
                    orientation = Orientation.Horizontal,
                    onDragStarted = { coordinator.openKey = key },
                    onDragStopped = { velocity ->
                        val v = offset
                        val target = when {
                            velocity > 500f && v > 0f -> maxRight
                            velocity < -500f && v < 0f -> maxLeft
                            v > 0f && v > maxRight / 2 -> maxRight
                            v < 0f && v < maxLeft / 2 -> maxLeft
                            else -> 0f
                        }
                        settle(target)
                    },
                ),
        ) {
            content()
            // While open, a tap anywhere on the row just closes it.
            if (abs(offset) > 1f) {
                Box(
                    Modifier
                        .matchParentSize()
                        .clickable(
                            interactionSource = remember { MutableInteractionSource() },
                            indication = null,
                        ) { settle(0f) }
                )
            }
        }
    }
}

@Composable
private fun ActionStrip(
    actions: List<SwipeAction>,
    width: Dp,
    onTap: (SwipeAction) -> Unit,
) {
    Row(Modifier.width(width).fillMaxHeight()) {
        actions.forEach { action ->
            Column(
                modifier = Modifier
                    .weight(action.width.value)
                    .fillMaxHeight()
                    .background(action.color)
                    .clickable { onTap(action) }
                    .padding(horizontal = 4.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Icon(action.icon, null, tint = Color.White, modifier = Modifier.size(22.dp))
                Spacer(Modifier.height(4.dp))
                Text(
                    action.label,
                    style = Ios.type.footnote.copy(fontWeight = FontWeight.Medium),
                    color = Color.White,
                    maxLines = 2,
                    textAlign = TextAlign.Center,
                    overflow = TextOverflow.Clip,
                )
            }
        }
    }
}

/** Closes any open swipe row when the list starts scrolling (UITableView does). */
@Composable
fun CloseSwipesOnScroll(isScrolling: Boolean) {
    val coordinator = LocalSwipeCoordinator.current
    LaunchedEffect(isScrolling) { if (isScrolling) coordinator.openKey = null }
}
