package com.giovannicoppola.whowaswhen

import android.app.Application
import coil.ImageLoader
import coil.ImageLoaderFactory
import okhttp3.OkHttpClient

/**
 * Provides the app-wide Coil [ImageLoader]. Wikimedia's image host
 * (`upload.wikimedia.org`) returns HTTP 403 to requests without a descriptive
 * User-Agent, so every image download must carry one — the same identification
 * the Wikipedia REST API calls use.
 */
class WwwApp : Application(), ImageLoaderFactory {
    override fun newImageLoader(): ImageLoader {
        val client = OkHttpClient.Builder()
            .addInterceptor { chain ->
                val request = chain.request().newBuilder()
                    .header(
                        "User-Agent",
                        "WhoWasWhen-Android/1.1 (https://github.com/giovannicoppola/alfred-WhoWasWhen)"
                    )
                    .build()
                chain.proceed(request)
            }
            .build()

        return ImageLoader.Builder(this)
            .okHttpClient(client)
            .crossfade(true)
            .build()
    }
}
