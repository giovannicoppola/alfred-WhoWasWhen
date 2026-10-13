package com.giovannicoppola.whowaswhen.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.view.HapticFeedbackConstants
import android.view.View
import androidx.compose.runtime.staticCompositionLocalOf
import com.giovannicoppola.whowaswhen.WwwViewModel
import com.giovannicoppola.whowaswhen.model.SearchResult

/**
 * The navigation + data actions a result row / card can invoke — the Android
 * counterpart of the iOS AppModel navigation methods. Provided app-wide via
 * [LocalAppActions] so rows don't need every callback threaded through.
 */
class AppActions(
    val vm: WwwViewModel,
    private val context: Context,
    private val view: View,
) {
    fun travel(year: Int) = vm.travel(year)
    fun showLineage(result: SearchResult) = vm.showLineage(result)
    fun showDetail(result: SearchResult) = vm.showDetail(result)
    fun toggleFavorite(result: SearchResult) = vm.toggleFavorite(result)

    /** Copies a result and confirms with a success haptic + brief banner. */
    fun copy(result: SearchResult) {
        vm.copyToClipboard(result)
        hapticSuccess()
    }

    fun openUrl(url: String) {
        runCatching {
            context.startActivity(
                Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            )
        }
    }

    fun share(text: String, title: String) {
        val send = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, text)
        }
        runCatching { context.startActivity(Intent.createChooser(send, title)) }
    }

    // UINotificationFeedbackGenerator equivalents.
    fun hapticSuccess() = view.performHapticFeedback(
        if (Build.VERSION.SDK_INT >= 30) HapticFeedbackConstants.CONFIRM
        else HapticFeedbackConstants.VIRTUAL_KEY
    )

    fun hapticError() = view.performHapticFeedback(
        if (Build.VERSION.SDK_INT >= 30) HapticFeedbackConstants.REJECT
        else HapticFeedbackConstants.LONG_PRESS
    )

    fun hapticLongPress() = view.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
}

val LocalAppActions = staticCompositionLocalOf<AppActions> {
    error("AppActions not provided")
}
