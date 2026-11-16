package org.recoverx.mobile

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DiskImagePolicyTest {
    @Test
    fun acceptsImageSuffixesCaseInsensitively() {
        assertTrue(DiskImagePolicy.isSupportedName("camera.DD"))
        assertTrue(DiskImagePolicy.isSupportedName("archive.iso"))
    }

    @Test
    fun rejectsUnrecognizedNames() {
        assertFalse(DiskImagePolicy.isSupportedName("photo.jpg"))
        assertFalse(DiskImagePolicy.isSupportedName("disk"))
        assertFalse(DiskImagePolicy.isSupportedName("archive.e01"))
    }

    @Test
    fun onlyRejectsSizeWhenProviderConfirmsEmpty() {
        assertTrue(DiskImagePolicy.isKnownEmpty(0L))
        assertFalse(DiskImagePolicy.isKnownEmpty(null))
        assertFalse(DiskImagePolicy.isKnownEmpty(1024L))
    }
}
