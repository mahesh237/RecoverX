package org.recoverx.mobile

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.OpenableColumns
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

private val Ink = Color(0xFF09121F)
private val Panel = Color(0xFF121F31)
private val PanelRaised = Color(0xFF192A40)
private val Mint = Color(0xFF6BE0BE)
private val Muted = Color(0xFF9AAAC0)
private val Warning = Color(0xFFF2C36B)

data class SelectedDocument(
    val uri: Uri,
    val displayName: String,
    val sizeBytes: Long?,
    val mimeType: String?,
)

data class SelectedFolder(val uri: Uri, val displayName: String)

class MainActivity : ComponentActivity() {
    private val scanExecutor = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())
    private var activeCancellation: AtomicBoolean? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = darkColorScheme(
                background = Ink,
                surface = Panel,
                primary = Mint,
                onPrimary = Ink,
                onBackground = Color(0xFFF3F6FC),
                onSurface = Color(0xFFF3F6FC),
                secondary = Muted,
            )) {
                RecoverXMobileScreen(
                    readDocument = ::readDocument,
                    persistReadAccess = ::persistReadAccess,
                    persistFolderAccess = ::persistFolderAccess,
                    startScan = ::startScan,
                    cancelScan = ::cancelScan,
                )
            }
        }
    }

    override fun onDestroy() {
        activeCancellation?.set(true)
        scanExecutor.shutdownNow()
        super.onDestroy()
    }

    private fun cancelScan() {
        activeCancellation?.set(true)
    }

    private fun startScan(source: SelectedDocument, destination: SelectedFolder, report: (String) -> Unit) {
        val cancellation = AtomicBoolean(false)
        activeCancellation = cancellation
        scanExecutor.execute {
            try {
                val result = ImageCarver(contentResolver).scan(
                    source.uri, destination.uri, cancellation,
                ) { bytes, files ->
                    mainHandler.post {
                        report("Scanned ${formatBytes(bytes)} · $files complete file${if (files == 1) "" else "s"} found")
                    }
                }
                val status = when {
                    result.cancelled -> "Scan stopped. ${result.files} complete file${if (result.files == 1) "" else "s"} saved."
                    result.files == 0 -> "Scan finished. No complete JPEG or PNG files were found."
                    else -> "Scan finished. ${result.files} complete file${if (result.files == 1) "" else "s"} saved to the chosen folder."
                }
                mainHandler.post { report(status) }
            } catch (error: Exception) {
                mainHandler.post { report("Scan failed: ${error.message ?: "the selected file or folder is unavailable."}") }
            } finally {
                activeCancellation = null
            }
        }
    }

    private fun persistReadAccess(uri: Uri) {
        try {
            contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
        } catch (_: SecurityException) {
            // Some document providers grant temporary access only; keep this selection for this session.
        }
    }

    private fun persistFolderAccess(uri: Uri) {
        try {
            contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
            )
        } catch (_: SecurityException) {
            // Some document providers grant temporary folder access only.
        }
    }

    private fun readDocument(uri: Uri): SelectedDocument {
        var name = uri.lastPathSegment?.substringAfterLast('/') ?: "Selected disk image"
        var size: Long? = null
        contentResolver.query(uri, null, null, null, null)?.use { cursor ->
            val nameColumn = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            val sizeColumn = cursor.getColumnIndex(OpenableColumns.SIZE)
            if (cursor.moveToFirst()) {
                if (nameColumn >= 0) name = cursor.getString(nameColumn) ?: name
                if (sizeColumn >= 0 && !cursor.isNull(sizeColumn)) size = cursor.getLong(sizeColumn)
            }
        }
        return SelectedDocument(uri, name, size, contentResolver.getType(uri))
    }
}

@Composable
private fun RecoverXMobileScreen(
    readDocument: (Uri) -> SelectedDocument,
    persistReadAccess: (Uri) -> Unit,
    persistFolderAccess: (Uri) -> Unit,
    startScan: (SelectedDocument, SelectedFolder, (String) -> Unit) -> Unit,
    cancelScan: () -> Unit,
) {
    var selectedDocument by remember { mutableStateOf<SelectedDocument?>(null) }
    var selectedFolder by remember { mutableStateOf<SelectedFolder?>(null) }
    var validationMessage by remember { mutableStateOf<String?>(null) }
    var scanMessage by remember { mutableStateOf<String?>(null) }
    var scanning by remember { mutableStateOf(false) }

    val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            persistReadAccess(uri)
            val document = readDocument(uri)
            selectedDocument = document
            validationMessage = when {
                !DiskImagePolicy.isSupportedName(document.displayName) -> "Choose a raw image ending in IMG, DD, RAW, 001, or ISO."
                DiskImagePolicy.isKnownEmpty(document.sizeBytes) -> "The selected file is empty."
                else -> null
            }
        }
    }
    val destinationPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        if (uri != null) {
            persistFolderAccess(uri)
            val name = uri.lastPathSegment?.substringAfterLast(':')?.takeIf { it.isNotBlank() } ?: "Selected folder"
            selectedFolder = SelectedFolder(uri, name)
        }
    }

    Surface(modifier = Modifier.fillMaxSize(), color = Ink) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp, vertical = 18.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            TopBar()
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Recover what matters.", fontSize = 31.sp, lineHeight = 36.sp, fontWeight = FontWeight.Bold)
                Text("A private, image-first recovery workspace for Android.", color = Muted, fontSize = 15.sp)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatusPill("ON DEVICE", Mint)
                StatusPill("NO ACCOUNT", Muted)
                StatusPill("ANDROID", Muted)
            }

            SectionCard {
                SectionEyebrow("01  ·  SOURCE IMAGE", "Select a disk image")
                Text("Choose a file you own from this device, an SD card, or a connected storage provider.", color = Muted, fontSize = 14.sp)
                selectedDocument?.let { DocumentSummary(it) }
                validationMessage?.let { InlineMessage(it, Warning) }
                OutlinedButton(
                    onClick = { imagePicker.launch(arrayOf("*/*")) },
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = Mint),
                ) {
                    Text(if (selectedDocument == null) "Browse for image" else "Choose another image")
                }
            }

            SectionCard {
                SectionEyebrow("02  ·  SAFE DESTINATION", "Choose a recovery folder")
                Text(selectedFolder?.displayName ?: "Pick a folder where future recovered files can be saved.", color = Muted, fontSize = 14.sp)
                OutlinedButton(
                    onClick = { destinationPicker.launch(null) },
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = Mint),
                ) {
                    Text(if (selectedFolder == null) "Choose folder" else "Change folder")
                }
                Text(
                    "The scan engine will require a destination on storage separate from the source image.",
                    color = Muted,
                    fontSize = 12.sp,
                    lineHeight = 17.sp,
                )
            }

            SectionCard {
                SectionEyebrow("RECOVERY ENGINE", "Carve JPEG and PNG files")
                Text(
                    "Scans the selected image sequentially for complete, contiguous JPEG and PNG files. Fragmented files, other formats, and phone internal storage are not supported by this first engine.",
                    color = Muted,
                    fontSize = 14.sp,
                    lineHeight = 20.sp,
                )
                scanMessage?.let { InlineMessage(it, if (it.startsWith("Scan failed")) Warning else Mint) }
                Button(
                    onClick = {
                        val source = selectedDocument
                        val destination = selectedFolder
                        if (!scanning && source != null && destination != null && validationMessage == null) {
                            scanning = true
                            scanMessage = "Starting scan…"
                            startScan(source, destination) { message ->
                                scanMessage = message
                                if (!message.startsWith("Scanned ") && message != "Starting scan…") scanning = false
                            }
                        } else if (scanning) {
                            cancelScan()
                        }
                    },
                    enabled = (selectedDocument != null && selectedFolder != null && validationMessage == null) || scanning,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(14.dp),
                ) {
                    Text(if (scanning) "Stop scan" else "Scan image", modifier = Modifier.padding(vertical = 4.dp))
                }
            }

            SectionCard {
                Text("A note about phone storage", fontWeight = FontWeight.SemiBold, fontSize = 16.sp)
                Text(
                    "Android limits apps to their own data and files you explicitly select. RecoverX cannot scan private app data or raw internal storage. Choose a disk image you own and save results in a separate destination.",
                    color = Muted,
                    fontSize = 13.sp,
                    lineHeight = 19.sp,
                )
            }
            Text("RECOVERX MOBILE  ·  EARLY ACCESS", color = Muted, fontSize = 11.sp, letterSpacing = 1.2.sp)
        }
    }
}

@Composable
private fun TopBar() {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(11.dp)) {
        Surface(modifier = Modifier.size(42.dp), shape = RoundedCornerShape(14.dp), color = PanelRaised) {
            androidx.compose.foundation.layout.Box(contentAlignment = Alignment.Center) {
                Text("◈", color = Mint, fontSize = 24.sp, fontWeight = FontWeight.Bold)
            }
        }
        Column(modifier = Modifier.weight(1f)) {
            Text("RecoverX", fontSize = 19.sp, fontWeight = FontWeight.Bold)
            Text("MOBILE RECOVERY", color = Muted, fontSize = 10.sp, letterSpacing = 1.5.sp)
        }
        Surface(shape = CircleShape, color = Color(0xFF193B39)) {
            Text("LOCAL", modifier = Modifier.padding(horizontal = 11.dp, vertical = 7.dp), color = Mint, fontSize = 10.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun StatusPill(label: String, color: Color) {
    Surface(shape = RoundedCornerShape(50), color = PanelRaised) {
        Text(label, modifier = Modifier.padding(horizontal = 10.dp, vertical = 7.dp), color = color, fontSize = 9.sp, fontWeight = FontWeight.Bold, letterSpacing = 0.8.sp)
    }
}

@Composable
private fun SectionCard(content: @Composable () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(22.dp),
        colors = CardDefaults.cardColors(containerColor = Panel),
    ) {
        Column(modifier = Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(13.dp)) {
            content()
        }
    }
}

@Composable
private fun SectionEyebrow(eyebrow: String, title: String) {
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(eyebrow, color = Mint, fontSize = 10.sp, letterSpacing = 1.2.sp, fontWeight = FontWeight.Bold)
        Text(title, fontSize = 18.sp, lineHeight = 23.sp, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun DocumentSummary(document: SelectedDocument) {
    Surface(shape = RoundedCornerShape(14.dp), color = PanelRaised) {
        Column(modifier = Modifier.fillMaxWidth().padding(13.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(document.displayName, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            val size = document.sizeBytes?.let(::formatBytes) ?: "Size not reported by provider"
            Text("$size${document.mimeType?.let { "  ·  $it" } ?: ""}", color = Muted, fontSize = 12.sp)
        }
    }
}

@Composable
private fun InlineMessage(message: String, color: Color) {
    Text(message, color = color, fontSize = 12.sp, lineHeight = 17.sp)
}

private fun formatBytes(bytes: Long): String {
    if (bytes < 1024) return "$bytes B"
    var value = bytes.toDouble()
    val units = listOf("KB", "MB", "GB", "TB")
    for (unit in units) {
        value /= 1024.0
        if (value < 1024.0 || unit == units.last()) return "%.1f %s".format(value, unit)
    }
    return "$bytes B"
}
