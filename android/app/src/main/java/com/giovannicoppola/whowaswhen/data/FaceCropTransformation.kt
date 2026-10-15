package com.giovannicoppola.whowaswhen.data

import android.graphics.Bitmap
import android.graphics.PointF
import android.graphics.Rect
import android.media.FaceDetector
import coil.size.Size
import coil.transform.Transformation

/**
 * A Coil transformation that crops a portrait to a face-centered square.
 *
 * Historical portraits are tall with the head near the top, so a naive center
 * crop routinely decapitates them (Henry VIII). This mirrors the iOS Vision
 * crop: ML Kit face detection re-centers the square on the union of detected
 * faces; images with no detectable face fall back to a top-anchored crop.
 */
class FaceCropTransformation : Transformation {

    override val cacheKey: String = "face-crop"

    override suspend fun transform(input: Bitmap, size: Size): Bitmap {
        val w = input.width
        val h = input.height
        val side = minOf(w, h)
        if (side <= 0 || w == h) return input

        var originX = (w - side) / 2
        var originY = 0

        faceUnion(input)?.let { face ->
            originX = (face.centerX() - side / 2).coerceIn(0, w - side)
            originY = (face.centerY() - side / 2).coerceIn(0, h - side)
        }

        return Bitmap.createBitmap(input, originX, originY, side, side)
    }

    private fun faceUnion(bitmap: Bitmap): Rect? = try {
        // FaceDetector needs an RGB_565 bitmap with an even width.
        val even = bitmap.width and 1.inv()
        val src = if (even == bitmap.width) bitmap
        else Bitmap.createBitmap(bitmap, 0, 0, even, bitmap.height)
        val rgb565 = src.copy(Bitmap.Config.RGB_565, false)
        val faces = arrayOfNulls<FaceDetector.Face>(MAX_FACES)
        val found = FaceDetector(rgb565.width, rgb565.height, MAX_FACES).findFaces(rgb565, faces)
        var union: Rect? = null
        val mid = PointF()
        for (i in 0 until found) {
            val face = faces[i] ?: continue
            face.getMidPoint(mid)
            // The detector reports the point between the eyes; approximate the
            // head as a box around it, nudged down toward the face's center.
            val r = face.eyesDistance() * 1.5f
            val cy = mid.y + face.eyesDistance() * 0.4f
            val box = Rect((mid.x - r).toInt(), (cy - r).toInt(), (mid.x + r).toInt(), (cy + r).toInt())
            union = union?.apply { union(box) } ?: box
        }
        union
    } catch (e: Exception) {
        null
    }

    override fun equals(other: Any?): Boolean = other is FaceCropTransformation

    override fun hashCode(): Int = cacheKey.hashCode()

    private companion object {
        const val MAX_FACES = 5
    }
}
