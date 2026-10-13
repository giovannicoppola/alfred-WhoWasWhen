package com.giovannicoppola.whowaswhen.ui

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material.icons.filled.AccountBalance
import androidx.compose.material.icons.filled.AccountBox
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material.icons.filled.Palette
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.filled.Science
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.PathBuilder
import androidx.compose.ui.graphics.vector.path
import androidx.compose.ui.unit.dp
import com.giovannicoppola.whowaswhen.model.ResultKind
import com.giovannicoppola.whowaswhen.model.SearchResult
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin

/** Maps a result to an icon, echoing the iOS per-title SF Symbols. */
object UiIcons {
    fun symbol(result: SearchResult): ImageVector {
        if (result.kind == ResultKind.EVENT) return Icons.Filled.CalendarMonth
        val t = (result.titleName ?: "").lowercase()
        return when {
            t.contains("pope") || t.contains("patriarch") || t.contains("antipope") -> SfIcons.CrossFill
            t.contains("president") -> Icons.Filled.AccountBox
            t.contains("prime minister") || t.contains("chancellor") || t.contains("premier") -> Icons.Filled.AccountBalance
            t.contains("consul") || t.contains("tribune") || t.contains("dictator") -> SfIcons.Laurel
            t.contains("artist") || t.contains("painter") -> Icons.Filled.Palette
            t.contains("composer") -> Icons.Filled.MusicNote
            t.contains("writer") -> Icons.AutoMirrored.Filled.MenuBook
            t.contains("scientist") -> Icons.Filled.Science
            t.contains("philosopher") -> Icons.Filled.Psychology
            else -> SfIcons.CrownFill
        }
    }

    @Composable
    fun tint(result: SearchResult): Color =
        if (result.kind == ResultKind.EVENT) Ios.colors.orange else Ios.colors.indigo
}

/**
 * Hand-drawn stand-ins for the SF Symbols that have no Material equivalent
 * (crown, cross, laurel, star-slash, the travel arrows). 24×24 viewport.
 */
object SfIcons {
    private fun icon(name: String, block: ImageVector.Builder.() -> Unit): ImageVector =
        ImageVector.Builder(name, 24.dp, 24.dp, 24f, 24f).apply(block).build()

    private val black = SolidColor(Color.Black)

    private fun ImageVector.Builder.stroke(width: Float = 1.8f, pathBuilder: PathBuilder.() -> Unit) =
        path(
            fill = null, stroke = black, strokeLineWidth = width,
            strokeLineCap = StrokeCap.Round, strokeLineJoin = StrokeJoin.Round,
            pathBuilder = pathBuilder,
        )

    private fun PathBuilder.circle(cx: Float, cy: Float, r: Float) {
        moveTo(cx - r, cy)
        arcTo(r, r, 0f, true, true, cx + r, cy)
        arcTo(r, r, 0f, true, true, cx - r, cy)
        close()
    }

    /** crown.fill */
    val CrownFill: ImageVector by lazy {
        icon("crown.fill") {
            path(fill = black) {
                moveTo(2.6f, 8.2f); lineTo(7.4f, 12.2f); lineTo(12f, 5.4f)
                lineTo(16.6f, 12.2f); lineTo(21.4f, 8.2f); lineTo(19.6f, 17.2f)
                lineTo(4.4f, 17.2f); close()
                circle(2.6f, 7.2f, 1.5f)
                circle(12f, 4.2f, 1.6f)
                circle(21.4f, 7.2f, 1.5f)
                moveTo(5f, 18.6f); lineTo(19f, 18.6f)
                arcTo(0.9f, 0.9f, 0f, false, true, 19f, 20.4f)
                lineTo(5f, 20.4f)
                arcTo(0.9f, 0.9f, 0f, false, true, 5f, 18.6f)
                close()
            }
        }
    }

    /** cross.fill — a Latin cross. */
    val CrossFill: ImageVector by lazy {
        icon("cross.fill") {
            path(fill = black) {
                moveTo(10.4f, 2f); lineTo(13.6f, 2f); lineTo(13.6f, 6.8f); lineTo(18.6f, 6.8f)
                lineTo(18.6f, 10f); lineTo(13.6f, 10f); lineTo(13.6f, 22f); lineTo(10.4f, 22f)
                lineTo(10.4f, 10f); lineTo(5.4f, 10f); lineTo(5.4f, 6.8f); lineTo(10.4f, 6.8f)
                close()
            }
        }
    }

    /** laurel.leading — a curved branch with leaves on both sides. */
    val Laurel: ImageVector by lazy {
        icon("laurel.leading") {
            // Stem: a quadratic arc bulging to the leading side.
            val p0 = 15f to 22f
            val p1 = 5f to 14.5f
            val p2 = 11.5f to 2.5f
            fun at(t: Float): Pair<Float, Float> {
                val u = 1 - t
                return (u * u * p0.first + 2 * u * t * p1.first + t * t * p2.first) to
                    (u * u * p0.second + 2 * u * t * p1.second + t * t * p2.second)
            }
            fun tangent(t: Float): Float {
                val dx = 2 * (1 - t) * (p1.first - p0.first) + 2 * t * (p2.first - p1.first)
                val dy = 2 * (1 - t) * (p1.second - p0.second) + 2 * t * (p2.second - p1.second)
                return atan2(dy, dx)
            }
            stroke(1.4f) {
                moveTo(p0.first, p0.second)
                quadTo(p1.first, p1.second, p2.first, p2.second)
            }
            path(fill = black) {
                fun leaf(t: Float, side: Float, len: Float) {
                    val (bx, by) = at(t)
                    val a = tangent(t) + side * 0.75f
                    val dx = cos(a); val dy = sin(a)
                    val nx = -dy; val ny = dx
                    val tipX = bx + dx * len; val tipY = by + dy * len
                    val mx = bx + dx * len / 2; val my = by + dy * len / 2
                    val w = len * 0.42f
                    moveTo(bx, by)
                    quadTo(mx + nx * w, my + ny * w, tipX, tipY)
                    quadTo(mx - nx * w, my - ny * w, bx, by)
                    close()
                }
                listOf(0.18f, 0.38f, 0.58f, 0.78f).forEach { leaf(it, -1f, 5.2f) }
                listOf(0.28f, 0.48f, 0.68f).forEach { leaf(it, 1f, 4.4f) }
                leaf(0.98f, 0f, 4f)
            }
        }
    }

    /** star.slash — outline star struck through. */
    val StarSlash: ImageVector by lazy {
        icon("star.slash") {
            stroke(1.6f) {
                val cx = 12f; val cy = 12.6f
                for (i in 0 until 10) {
                    val r = if (i % 2 == 0) 9.6f else 4.1f
                    val a = Math.toRadians(-90.0 + i * 36.0)
                    val x = cx + r * cos(a).toFloat(); val y = cy + r * sin(a).toFloat()
                    if (i == 0) moveTo(x, y) else lineTo(x, y)
                }
                close()
                moveTo(3f, 3f); lineTo(21f, 21f)
            }
        }
    }

    /** arrow.forward.to.line — →| */
    val ArrowForwardToLine: ImageVector by lazy {
        icon("arrow.forward.to.line") {
            stroke {
                moveTo(20.5f, 5f); lineTo(20.5f, 19f)
                moveTo(3f, 12f); lineTo(16.5f, 12f)
                moveTo(11.5f, 7f); lineTo(16.5f, 12f); lineTo(11.5f, 17f)
            }
        }
    }

    /** arrow.backward.to.line — |← */
    val ArrowBackwardToLine: ImageVector by lazy {
        icon("arrow.backward.to.line") {
            stroke {
                moveTo(3.5f, 5f); lineTo(3.5f, 19f)
                moveTo(21f, 12f); lineTo(7.5f, 12f)
                moveTo(12.5f, 7f); lineTo(7.5f, 12f); lineTo(12.5f, 17f)
            }
        }
    }

    /** chevron.left — the navigation-bar back chevron. */
    val ChevronLeft: ImageVector by lazy {
        icon("chevron.left") {
            stroke(2.6f) {
                moveTo(15.5f, 3.5f); lineTo(7f, 12f); lineTo(15.5f, 20.5f)
            }
        }
    }

    /** chevron.right — disclosure indicator. */
    val ChevronRight: ImageVector by lazy {
        icon("chevron.right") {
            stroke(2.6f) {
                moveTo(8.5f, 3.5f); lineTo(17f, 12f); lineTo(8.5f, 20.5f)
            }
        }
    }
}
