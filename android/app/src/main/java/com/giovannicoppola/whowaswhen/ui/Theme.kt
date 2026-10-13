package com.giovannicoppola.whowaswhen.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import com.giovannicoppola.whowaswhen.R

/**
 * The iOS app's look, rebuilt for Compose: Apple's system colors (light and
 * dark), the asset-catalog accent, and the Dynamic Type text styles. Screens
 * read these through [Ios] rather than Material's color scheme so the two
 * apps match side by side.
 */
@Immutable
data class IosColors(
    val accent: Color,
    val background: Color,              // systemBackground
    val secondaryBackground: Color,     // secondarySystemBackground
    val groupedBackground: Color,       // systemGroupedBackground
    val groupedCell: Color,             // secondarySystemGroupedBackground
    val label: Color,
    val secondaryLabel: Color,
    val tertiaryLabel: Color,
    val separator: Color,
    val fill: Color,                    // tertiarySystemFill (search field, segmented track)
    val secondaryFill: Color,           // Color.secondary.opacity(0.14)-style chips
    val chrome: Color,                  // tab bar
    val segmentThumb: Color,
    val indigo: Color,
    val orange: Color,
    val yellow: Color,
    val green: Color,
    val red: Color,
    val teal: Color,
    val blue: Color,
    val purple: Color,
    val pink: Color,
    val gray: Color,
    val isDark: Boolean,
)

/** AccentColor.colorset — a single universal slate blue (no dark variant). */
private val Accent = Color(0xFF4B588B)

private val LightIos = IosColors(
    accent = Accent,
    background = Color.White,
    secondaryBackground = Color(0xFFF2F2F7),
    groupedBackground = Color(0xFFF2F2F7),
    groupedCell = Color.White,
    label = Color.Black,
    secondaryLabel = Color(0x993C3C43),
    tertiaryLabel = Color(0x4D3C3C43),
    separator = Color(0x4A3C3C43),
    fill = Color(0x1F767680),
    secondaryFill = Color(0x248E8E93),
    chrome = Color(0xF0F9F9F9),
    segmentThumb = Color.White,
    indigo = Color(0xFF5856D6),
    orange = Color(0xFFFF9500),
    yellow = Color(0xFFFFCC00),
    green = Color(0xFF34C759),
    red = Color(0xFFFF3B30),
    teal = Color(0xFF30B0C7),
    blue = Color(0xFF007AFF),
    purple = Color(0xFFAF52DE),
    pink = Color(0xFFFF2D55),
    gray = Color(0xFF8E8E93),
    isDark = false,
)

private val DarkIos = IosColors(
    accent = Accent,
    background = Color.Black,
    secondaryBackground = Color(0xFF1C1C1E),
    groupedBackground = Color.Black,
    groupedCell = Color(0xFF1C1C1E),
    label = Color.White,
    secondaryLabel = Color(0x99EBEBF5),
    tertiaryLabel = Color(0x4DEBEBF5),
    separator = Color(0x99545458),
    fill = Color(0x3D767680),
    secondaryFill = Color(0x2E8E8E93),
    chrome = Color(0xF0161616),
    segmentThumb = Color(0xFF636366),
    indigo = Color(0xFF5E5CE6),
    orange = Color(0xFFFF9F0A),
    yellow = Color(0xFFFFD60A),
    green = Color(0xFF30D158),
    red = Color(0xFFFF453A),
    teal = Color(0xFF40C8E0),
    blue = Color(0xFF0A84FF),
    purple = Color(0xFFBF5AF2),
    pink = Color(0xFFFF375F),
    gray = Color(0xFF8E8E93),
    isDark = true,
)

@OptIn(androidx.compose.ui.text.ExperimentalTextApi::class)
/** Inter — the closest freely licensed match for SF Pro's metrics and shapes. */
private fun interFont(weight: Int, italic: Boolean) = Font(
    resId = if (italic) R.font.inter_variable_italic else R.font.inter_variable,
    weight = FontWeight(weight),
    style = if (italic) FontStyle.Italic else FontStyle.Normal,
    variationSettings = FontVariation.Settings(FontVariation.weight(weight)),
)

val Inter = FontFamily(
    listOf(400, 500, 600, 700, 800).flatMap { w -> listOf(interFont(w, false), interFont(w, true)) }
)

/** SF-style tracking: slightly loose at small sizes, tight at display sizes. */
private fun style(size: Int, weight: FontWeight = FontWeight.Normal, tracking: TextUnit) = TextStyle(
    fontFamily = Inter,
    fontSize = size.sp,
    fontWeight = weight,
    letterSpacing = tracking,
    lineHeight = (size * 1.25f).sp,
)

/** The iOS Dynamic Type styles at the default ("Large") size. */
@Immutable
data class IosTypography(
    val largeTitle: TextStyle = style(34, FontWeight.Bold, 0.01.em),
    val title2: TextStyle = style(22, FontWeight.Bold, (-0.01).em),
    val title3: TextStyle = style(20, FontWeight.Normal, (-0.01).em),
    val headline: TextStyle = style(17, FontWeight.SemiBold, (-0.02).em),
    val body: TextStyle = style(17, FontWeight.Normal, (-0.02).em),
    val subheadline: TextStyle = style(15, FontWeight.Normal, (-0.01).em),
    val footnote: TextStyle = style(13, FontWeight.Normal, 0.em),
    val caption: TextStyle = style(12, FontWeight.Normal, 0.em),
    val caption2: TextStyle = style(11, FontWeight.Normal, 0.01.em),
    val tabLabel: TextStyle = style(10, FontWeight.Medium, 0.01.em),
)

private val LocalIosColors = staticCompositionLocalOf { LightIos }
private val LocalIosTypography = staticCompositionLocalOf { IosTypography() }

/** Access point for the iOS palette and text styles: `Ios.colors.accent`. */
object Ios {
    val colors: IosColors
        @Composable get() = LocalIosColors.current
    val type: IosTypography
        @Composable get() = LocalIosTypography.current
}

/** `.monospacedDigit()` — tabular figures. */
fun TextStyle.monospacedDigit(): TextStyle = copy(fontFeatureSettings = "tnum")

@Composable
fun WhoWasWhenTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val ios = if (darkTheme) DarkIos else LightIos
    // Material components that remain (sheets, menus, pull-to-refresh) are
    // themed from the iOS palette so nothing reads as stock Material.
    val material = if (darkTheme) {
        darkColorScheme(
            primary = ios.accent, onPrimary = Color.White,
            background = ios.background, surface = ios.background,
            onBackground = ios.label, onSurface = ios.label,
            surfaceVariant = ios.secondaryBackground, onSurfaceVariant = ios.secondaryLabel,
            surfaceContainer = ios.groupedCell, surfaceContainerLow = ios.groupedBackground,
            surfaceContainerHigh = ios.groupedCell, outlineVariant = ios.separator,
        )
    } else {
        lightColorScheme(
            primary = ios.accent, onPrimary = Color.White,
            background = ios.background, surface = ios.background,
            onBackground = ios.label, onSurface = ios.label,
            surfaceVariant = ios.secondaryBackground, onSurfaceVariant = ios.secondaryLabel,
            surfaceContainer = ios.groupedCell, surfaceContainerLow = ios.groupedBackground,
            surfaceContainerHigh = ios.groupedCell, outlineVariant = ios.separator,
        )
    }
    val type = IosTypography()
    CompositionLocalProvider(LocalIosColors provides ios, LocalIosTypography provides type) {
        MaterialTheme(
            colorScheme = material,
            typography = MaterialTheme.typography.copy(
                bodyLarge = type.body, bodyMedium = type.subheadline, bodySmall = type.footnote,
                labelLarge = type.body, labelMedium = type.footnote, labelSmall = type.caption2,
                titleMedium = type.headline, titleSmall = type.subheadline,
            ),
            content = content,
        )
    }
}
