package com.shopos.bills.form

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.ExifInterface
import java.io.File

private const val JPEG_QUALITY = 50
private const val MAX_IMAGE_EDGE = 3000

/** Reduce camera uploads while keeping bill text readable and its display orientation intact. */
fun compressProofPhoto(source: File): File {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeFile(source.absolutePath, bounds)
    require(bounds.outWidth > 0 && bounds.outHeight > 0) { "Could not read proof photo" }

    var sampleSize = 1
    while (maxOf(bounds.outWidth, bounds.outHeight) / sampleSize > MAX_IMAGE_EDGE) sampleSize *= 2
    val bitmap = BitmapFactory.decodeFile(
        source.absolutePath,
        BitmapFactory.Options().apply { inSampleSize = sampleSize },
    ) ?: error("Could not read proof photo")
    val output = File.createTempFile("bill-proof-", ".jpg", source.parentFile)
    try {
        val orientation = ExifInterface(source.absolutePath).getAttribute(ExifInterface.TAG_ORIENTATION)
        output.outputStream().use { stream ->
            check(bitmap.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, stream)) { "Could not compress proof photo" }
        }
        if (orientation != null) {
            ExifInterface(output.absolutePath).apply {
                setAttribute(ExifInterface.TAG_ORIENTATION, orientation)
                saveAttributes()
            }
        }
        check(output.length() in 1..15_000_000) { "Compressed photo must be under 15 MB" }
        return output
    } catch (error: Exception) {
        output.delete()
        throw error
    } finally {
        bitmap.recycle()
    }
}
