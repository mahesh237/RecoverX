# RecoverX Android app

The Android app lives in `android/` as a separate Kotlin and Jetpack Compose application. It currently includes a user-authorized disk-image workflow and a limited on-device file carver:

- Select a raw disk-image file through Android's Storage Access Framework (`.img`, `.dd`, `.raw`, `.001`, `.iso`).
- Display its provider-reported name, size, and MIME type.
- Select a folder for a future recovery destination.
- Sequentially scan the selected image for complete, contiguous JPEG and PNG files and save them into the selected folder.
- Show scan progress and allow the current scan to be stopped.

The app requests only the URI permissions returned by the system pickers. It declares no broad storage permission or Internet permission. A document provider may represent local or provider-managed content; the app itself does not upload data.

PhotoRec is not yet ported or bundled for Android. The current Kotlin engine is a narrow signature carver, not a partition-aware filesystem recovery engine: it handles contiguous JPEG and PNG files only, skips incomplete candidates and candidates larger than 256 MiB, and cannot reconstruct fragmented files or recover directory names and metadata. It reads the selected raw image sequentially and writes completed files to the selected folder. The user must select a destination on storage separate from the source; Android providers do not always expose enough information to verify that they are physically separate. The app does not scan phone-internal storage or other apps' private files. Android's scoped storage and per-app sandbox mean that broad raw-storage recovery is not generally available to an ordinary app.

The Android implementation is separate from the existing Python desktop app; it does not reuse the desktop UI or claim the desktop PhotoRec integration works on phones.

## Build

Open `android/` in Android Studio, install Android SDK Platform 36 and Build Tools 36.0.0, then build the `app` debug variant. Or, from the repository root:

```powershell
cd android
.\gradlew.bat assembleDebug testDebugUnitTest
```

The Android Actions workflow builds and tests the app and uploads `app-debug.apk` as the `recoverx-android-debug` artifact.

No broad storage permission or network permission is declared. Source files and folders are selected through system pickers.
