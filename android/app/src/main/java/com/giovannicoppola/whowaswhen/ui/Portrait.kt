package com.giovannicoppola.whowaswhen.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil.compose.SubcomposeAsyncImage
import coil.request.ImageRequest
import com.giovannicoppola.whowaswhen.data.FaceCropTransformation
import com.giovannicoppola.whowaswhen.data.WikipediaClient
import com.giovannicoppola.whowaswhen.model.SearchResult

/**
 * A circular Wikipedia thumbnail for a ruler or event, falling back to the
 * result's Material icon while loading, offline, or when the page has no image.
 * Images are face-centered by [FaceCropTransformation] so heads stay in frame.
 */
@Composable
fun PortraitView(result: SearchResult, size: Dp = 40.dp) {
    val context = LocalContext.current
    var thumbUrl by remember(result.wikipediaUrl) { mutableStateOf<String?>(null) }

    LaunchedEffect(result.wikipediaUrl) {
        thumbUrl = null
        val page = result.wikipediaUrl ?: return@LaunchedEffect
        thumbUrl = WikipediaClient.summary(page)?.thumbnailUrl
    }

    val fallback: @Composable () -> Unit = {
        Box(
            modifier = Modifier
                .size(size)
                .clip(CircleShape)
                .background(UiIcons.tint(result).copy(alpha = 0.12f)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = UiIcons.symbol(result),
                contentDescription = null,
                tint = UiIcons.tint(result),
                modifier = Modifier.size(size * 0.5f),
            )
        }
    }

    val url = thumbUrl
    if (url == null) {
        fallback()
    } else {
        SubcomposeAsyncImage(
            model = ImageRequest.Builder(context)
                .data(url)
                .transformations(FaceCropTransformation())
                .crossfade(true)
                .build(),
            contentDescription = result.title,
            contentScale = ContentScale.Crop,
            loading = { fallback() },
            error = { fallback() },
            modifier = Modifier
                .size(size)
                .clip(CircleShape),
        )
    }
}
