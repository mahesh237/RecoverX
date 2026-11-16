package org.recoverx.mobile

import android.content.ContentResolver
import android.net.Uri
import android.provider.DocumentsContract
import java.io.BufferedInputStream
import java.io.InputStream
import java.io.OutputStream
import java.util.concurrent.atomic.AtomicBoolean

/** A conservative, sequential carver for contiguous JPEG and PNG files in a disk image. */
class ImageCarver(private val resolver: ContentResolver) {
    data class Result(val files: Int, val bytesScanned: Long, val cancelled: Boolean)

    fun scan(
        source: Uri,
        destinationTree: Uri,
        cancelled: AtomicBoolean,
        onProgress: (Long, Int) -> Unit = { _, _ -> },
    ): Result {
        require(source != destinationTree) { "Choose a destination separate from the source." }
        val input = resolver.openInputStream(source) ?: error("Could not open the selected image.")
        input.use { stream -> return scanStream(stream, destinationTree, cancelled, onProgress) }
    }

    internal fun scanStream(
        source: InputStream,
        destinationTree: Uri,
        cancelled: AtomicBoolean,
        onProgress: (Long, Int) -> Unit = { _, _ -> },
    ): Result {
        val stream = BufferedInputStream(source, BUFFER_SIZE)
        var scanned = 0L
        var recovered = 0
        var candidate: Candidate? = null
        var output: OutputStream? = null
        var outputUri: Uri? = null
        var candidateBytes = 0L
        val tail = ArrayDeque<Int>()
        val prefix = ArrayDeque<Int>()
        var lastProgress = 0L
        var stopped = false

        fun discardCandidate() {
            runCatching { output?.close() }
            output = null
            outputUri?.let { runCatching { DocumentsContract.deleteDocument(resolver, it) } }
            outputUri = null
            candidate = null
            candidateBytes = 0L
            tail.clear()
        }

        try {
            while (!cancelled.get()) {
                val next = stream.read()
                if (next < 0) break
                val byte = next and 0xff
                scanned++

                if (candidate == null) {
                    prefix.addLast(byte)
                    while (prefix.size > PNG_START.size) prefix.removeFirst()
                    val start = when {
                        endsWith(prefix, JPEG_START) -> Candidate.JPEG
                        endsWith(prefix, PNG_START) -> Candidate.PNG
                        else -> null
                    }
                    if (start != null) {
                        candidate = start
                        val mime = if (start == Candidate.JPEG) "image/jpeg" else "image/png"
                        val ext = if (start == Candidate.JPEG) "jpg" else "png"
                        val doc = DocumentsContract.createDocument(resolver, destinationTree, mime, "recovered_%04d.%s".format(recovered + 1, ext))
                            ?: error("The selected folder could not create recovery files.")
                        outputUri = doc
                        output = resolver.openOutputStream(doc, "w") ?: error("Could not write into the selected folder.")
                        val signature = if (start == Candidate.JPEG) JPEG_START else PNG_START
                        signature.forEach { output!!.write(it) }
                        candidateBytes = signature.size.toLong()
                        tail.clear()
                    }
                } else {
                    output!!.write(byte)
                    candidateBytes++
                    tail.addLast(byte)
                    while (tail.size > MAX_END_MARKER) tail.removeFirst()

                    val complete = when (candidate ?: continue) {
                        Candidate.JPEG -> endsWith(tail, JPEG_END)
                        Candidate.PNG -> endsWith(tail, PNG_END)
                    }
                    if (complete) {
                        output!!.flush()
                        output!!.close()
                        output = null
                        outputUri = null
                        recovered++
                        candidate = null
                        candidateBytes = 0L
                        tail.clear()
                        prefix.clear()
                    } else if (candidateBytes > MAX_FILE_BYTES) {
                        discardCandidate()
                    }
                }

                if (scanned - lastProgress >= PROGRESS_INTERVAL) {
                    onProgress(scanned, recovered)
                    lastProgress = scanned
                }
            }
            stopped = cancelled.get()
        } catch (error: Throwable) {
            discardCandidate()
            throw error
        } finally {
            if (candidate != null) discardCandidate()
        }
        onProgress(scanned, recovered)
        return Result(recovered, scanned, stopped)
    }

    private enum class Candidate { JPEG, PNG }

    private fun endsWith(values: Collection<Int>, marker: IntArray): Boolean {
        if (values.size < marker.size) return false
        val iterator = values.iterator()
        repeat(values.size - marker.size) { iterator.next() }
        for (expected in marker) if (iterator.next() != expected) return false
        return true
    }

    companion object {
        private const val BUFFER_SIZE = 64 * 1024
        private const val MAX_FILE_BYTES = 256L * 1024 * 1024
        private const val PROGRESS_INTERVAL = 4L * 1024 * 1024
        private const val MAX_END_MARKER = 8
        private val JPEG_START = intArrayOf(0xff, 0xd8, 0xff)
        private val JPEG_END = intArrayOf(0xff, 0xd9)
        private val PNG_START = intArrayOf(0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a)
        private val PNG_END = intArrayOf(0x49, 0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82)
    }
}
