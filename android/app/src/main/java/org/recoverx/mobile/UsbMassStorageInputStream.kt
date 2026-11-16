package org.recoverx.mobile

import android.hardware.usb.UsbConstants
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbDeviceConnection
import android.hardware.usb.UsbEndpoint
import android.hardware.usb.UsbInterface
import android.hardware.usb.UsbManager
import java.io.IOException
import java.io.InputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Read-only USB Mass Storage Bulk-Only Transport stream backed by SCSI READ(10). */
class UsbMassStorageInputStream private constructor(
    private val connection: UsbDeviceConnection,
    private val usbInterface: UsbInterface,
    private val inputEndpoint: UsbEndpoint,
    private val outputEndpoint: UsbEndpoint,
    private val blockSize: Int,
    val capacityBytes: Long,
) : InputStream() {
    private var position = 0L
    private var tag = 0
    private var closed = false

    override fun read(): Int {
        val one = ByteArray(1)
        val count = read(one, 0, 1)
        return if (count < 0) -1 else one[0].toInt() and 0xff
    }

    override fun read(buffer: ByteArray, offset: Int, length: Int): Int {
        check(!closed) { "The USB drive connection is closed." }
        if (offset < 0 || length < 0 || length > buffer.size - offset) throw IndexOutOfBoundsException()
        if (length == 0) return 0
        if (position >= capacityBytes) return -1

        val byteCount = minOf(length.toLong(), capacityBytes - position).toInt()
        val lba = position / blockSize
        val withinBlock = (position % blockSize).toInt()
        val blocks = (withinBlock + byteCount + blockSize - 1) / blockSize
        if (blocks > MAX_READ_BLOCKS) throw IOException("USB read request exceeded the supported block limit.")
        val data = readBlocks(lba, blocks)
        System.arraycopy(data, withinBlock, buffer, offset, byteCount)
        position += byteCount
        return byteCount
    }

    private fun readBlocks(lba: Long, blocks: Int): ByteArray {
        if (lba > 0xffff_ffffL || blocks !in 1..MAX_READ_BLOCKS) {
            throw IOException("This USB drive exceeds the supported SCSI READ(10) range.")
        }
        val cdb = ByteArray(10)
        cdb[0] = SCSI_READ_10.toByte()
        ByteBuffer.wrap(cdb).order(ByteOrder.BIG_ENDIAN).putInt(2, lba.toInt()).putShort(7, blocks.toShort())
        return command(cdb, blocks * blockSize, dataIn = true)
    }

    private fun command(cdb: ByteArray, dataLength: Int, dataIn: Boolean): ByteArray {
        val commandTag = ++tag
        val cbw = ByteBuffer.allocate(CBW_LENGTH).order(ByteOrder.LITTLE_ENDIAN)
        cbw.putInt(CBW_SIGNATURE)
        cbw.putInt(commandTag)
        cbw.putInt(dataLength)
        cbw.put(if (dataIn) 0x80.toByte() else 0.toByte())
        cbw.put(0) // LUN 0
        cbw.put(cdb.size.toByte())
        cbw.put(cdb.copyOf(CDB_LENGTH))
        transferExact(outputEndpoint, cbw.array(), 0, CBW_LENGTH)

        val data = ByteArray(dataLength)
        if (dataLength > 0) transferExact(inputEndpoint, data, 0, dataLength)

        val csw = ByteArray(CSW_LENGTH)
        transferExact(inputEndpoint, csw, 0, CSW_LENGTH)
        val status = ByteBuffer.wrap(csw).order(ByteOrder.LITTLE_ENDIAN)
        if (status.int != CSW_SIGNATURE || status.int != commandTag) {
            throw IOException("USB mass-storage response did not match the read request.")
        }
        if (status.int != 0) throw IOException("The USB drive returned an incomplete disk block.")
        if ((status.get().toInt() and 0xff) != 0) throw IOException("The USB drive could not read this disk block.")
        return data
    }

    private fun transferExact(endpoint: UsbEndpoint, buffer: ByteArray, offset: Int, length: Int) {
        var transferred = 0
        while (transferred < length) {
            val chunkLength = minOf(length - transferred, MAX_USB_TRANSFER)
            val count = connection.bulkTransfer(endpoint, buffer, offset + transferred, chunkLength, TRANSFER_TIMEOUT_MS)
            if (count <= 0) throw IOException("USB read failed or the drive was disconnected.")
            transferred += count
        }
    }

    override fun close() {
        if (closed) return
        closed = true
        runCatching { connection.releaseInterface(usbInterface) }
        connection.close()
    }

    companion object {
        private const val SCSI_READ_CAPACITY_10 = 0x25
        private const val SCSI_READ_10 = 0x28
        private const val CBW_SIGNATURE = 0x43425355
        private const val CSW_SIGNATURE = 0x53425355
        private const val CBW_LENGTH = 31
        private const val CSW_LENGTH = 13
        private const val CDB_LENGTH = 16
        private const val MAX_USB_TRANSFER = 16 * 1024
        private const val MAX_READ_BLOCKS = 128
        private const val TRANSFER_TIMEOUT_MS = 15_000

        fun isSupported(device: UsbDevice): Boolean = (0 until device.interfaceCount).any { index ->
            val intf = device.getInterface(index)
            intf.interfaceClass == UsbConstants.USB_CLASS_MASS_STORAGE &&
                intf.interfaceSubclass == 0x06 && intf.interfaceProtocol == 0x50
        }

        fun open(manager: UsbManager, device: UsbDevice): UsbMassStorageInputStream {
            val usbInterface = (0 until device.interfaceCount)
                .map(device::getInterface)
                .firstOrNull {
                    it.interfaceClass == UsbConstants.USB_CLASS_MASS_STORAGE &&
                        it.interfaceSubclass == 0x06 && it.interfaceProtocol == 0x50
                } ?: throw IOException("This USB device does not expose a supported SCSI mass-storage interface.")

            val input = (0 until usbInterface.endpointCount).map(usbInterface::getEndpoint).firstOrNull {
                it.type == UsbConstants.USB_ENDPOINT_XFER_BULK && it.direction == UsbConstants.USB_DIR_IN
            } ?: throw IOException("The USB mass-storage device has no bulk read endpoint.")
            val output = (0 until usbInterface.endpointCount).map(usbInterface::getEndpoint).firstOrNull {
                it.type == UsbConstants.USB_ENDPOINT_XFER_BULK && it.direction == UsbConstants.USB_DIR_OUT
            } ?: throw IOException("The USB mass-storage device has no command endpoint.")

            val connection = manager.openDevice(device) ?: throw IOException("Android could not open the USB drive.")
            if (!connection.claimInterface(usbInterface, true)) {
                connection.close()
                throw IOException("Android could not claim the USB drive interface.")
            }

            try {
                val probe = UsbMassStorageInputStream(connection, usbInterface, input, output, 512, 0)
                val capacity = probe.command(ByteArray(10).also { it[0] = SCSI_READ_CAPACITY_10.toByte() }, 8, dataIn = true)
                val parsed = ByteBuffer.wrap(capacity).order(ByteOrder.BIG_ENDIAN)
                val lastLba = parsed.int.toLong() and 0xffff_ffffL
                val blockSize = parsed.int
                if (lastLba == 0xffff_ffffL) throw IOException("USB drives larger than the SCSI READ CAPACITY(10) range are not supported yet.")
                if (blockSize !in 512..4096 || (blockSize and (blockSize - 1)) != 0) {
                    throw IOException("The USB drive reported an unsupported logical block size.")
                }
                return UsbMassStorageInputStream(
                    connection, usbInterface, input, output, blockSize, (lastLba + 1) * blockSize,
                )
            } catch (error: Exception) {
                runCatching { connection.releaseInterface(usbInterface) }
                connection.close()
                throw error
            }
        }
    }
}
