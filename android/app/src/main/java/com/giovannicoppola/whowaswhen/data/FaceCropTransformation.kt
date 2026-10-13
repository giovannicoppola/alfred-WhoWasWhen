package com.giovannicoppola.whowaswhen.data

import android.graphics.Bitmap
import android.graphics.Rect
import coil.size.Size
import coil.transform.Transformation
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions

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

    private fun faceUnion(bitmap: Bitmap): Rect? {
        val options = FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
            .build()
        val detector = FaceDetection.getClient(options)
        return try {
            val image = InputImage.fromBitmap(bitmap, 0)
            val faces = Tasks.await(detector.process(image))
            if (faces.isNullOrEmpty()) return null
            val union = Rect(faces[0].boundingBox)
            for (i in 1 until faces.size) union.union(faces[i].boundingBox)
            union
        } catch (e: Exception) {
            null
        } finally {
            detector.close()
        }
    }

    override fun equals(other: Any?): Boolean = other is FaceCropTransformation

    override fun hashCode(): Int = cacheKey.hashCode()
}
