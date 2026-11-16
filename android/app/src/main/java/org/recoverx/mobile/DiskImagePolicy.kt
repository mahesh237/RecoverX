package org.recoverx.mobile

/** Selection checks only; a supported suffix does not guarantee engine support. */
object DiskImagePolicy {
    private val acceptedExtensions = setOf("img", "dd", "raw", "001", "iso")

    fun isSupportedName(name: String): Boolean {
        val extension = name.substringAfterLast('.', missingDelimiterValue = "")
        return extension.lowercase() in acceptedExtensions
    }

    fun isKnownEmpty(sizeBytes: Long?): Boolean = sizeBytes == 0L
}
