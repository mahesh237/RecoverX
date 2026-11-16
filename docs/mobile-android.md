# RecoverX Android app

The Android app lives in `android/` as a separate Kotlin and Jetpack Compose application. The current first slice is a mobile dashboard and user-authorized document workflow:

- Select a disk-image file through Android's Storage Access Framework.
- Display its provider-reported name, size, and MIME type.
- Select a folder for a future recovery destination.
- Explain the image-only scope and unavailable scan engine honestly.

The app requests only the URI permissions returned by the system pickers. It declares no broad storage permission or Internet permission. A document provider may represent local or provider-managed content; the app itself does not upload data.

PhotoRec is not yet ported or bundled for Android. The scan button is intentionally disabled. The app does not scan phone-internal storage or other apps' private files. Android's scoped storage and per-app sandbox mean that broad raw-storage recovery is not generally available to an ordinary app. A future engine integration must work from user-authorized image or removable-media file descriptors, and must establish safe source/destination separation before writing.

The Android implementation is separate from the existing Python desktop app; it does not reuse the desktop UI or claim the desktop PhotoRec integration works on phones.

## Build

Open `android/` in Android Studio, install Android SDK Platform 36 and Build Tools 36.0.0, then build the `app` debug variant. Or, from the repository root:

```powershell
cd android
.\gradlew.bat assembleDebug testDebugUnitTest
```

The Android Actions workflow builds and tests the app and uploads `app-debug.apk` as the `recoverx-android-debug` artifact.

No broad storage permission or network permission is declared. Source files and folders are selected through system pickers.
