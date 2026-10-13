package com.giovannicoppola.whowaswhen

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.LaunchedEffect
import com.giovannicoppola.whowaswhen.ui.DebugHooks
import com.giovannicoppola.whowaswhen.ui.WhoWasWhenApp
import com.giovannicoppola.whowaswhen.ui.WhoWasWhenTheme
import android.graphics.Color as AndroidColor

class MainActivity : ComponentActivity() {
    private val viewModel: WwwViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        // Draw under transparent system bars, as iOS content runs under the
        // status bar; icons follow the light/dark appearance.
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.auto(AndroidColor.TRANSPARENT, AndroidColor.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.auto(AndroidColor.TRANSPARENT, AndroidColor.TRANSPARENT),
        )
        super.onCreate(savedInstanceState)
        if (BuildConfig.DEBUG && savedInstanceState == null) DebugHooks.read(intent, viewModel)
        setContent {
            WhoWasWhenTheme(darkTheme = DebugHooks.dark ?: isSystemInDarkTheme()) {
                WhoWasWhenApp(viewModel)
                if (BuildConfig.DEBUG) LaunchedEffect(Unit) { DebugHooks.openDetailIfRequested(viewModel) }
            }
        }
    }
}
