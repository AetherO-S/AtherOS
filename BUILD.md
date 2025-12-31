# How to Build & Release AETHER-OS

## One-Time Setup (Do This Once)

### 1. Install NSIS
- Download: https://nsis.sourceforge.io/Download
- Run installer with default settings

### 2. Install NSIS Plugins
Download these and extract the `.dll` files to:
`C:\Program Files (x86)\NSIS\Plugins\x86-ansi\`

- **inetc.dll**: https://nsis.sourceforge.io/Inetc_plug-in
- **nsisunz.dll**: https://nsis.sourceforge.io/Nsisunz_plug-in

---

## For Each Release

### Step 1: Package App Files
```cmd
cd AetherOS-v2.2
scripts\package-app-files.bat
```
This creates `aether-os-app-files.zip` (~2MB)

### Step 2: Build the Installer
```cmd
cd installer
"C:\Program Files (x86)\NSIS\makensis.exe" bootstrap-installer.nsi
```
This creates `AETHER-OS-Setup-2.2.0.exe` (~2MB)

### Step 3: Upload to GitHub Releases

1. Go to: https://github.com/AetherO-S/AetherOS/releases/new
2. Tag: `v2.2.0` (match your version)
3. Title: `AETHER-OS v2.2.0`
4. **Attach these files:**
   - `AETHER-OS-Setup-2.2.0.exe` (the installer)
   - `aether-os-app-files.zip` (required for installer to work)
   - `viral_studio.zip` (optional plugin)
5. Publish!

---

## What Users Experience

1. User downloads `AETHER-OS-Setup-2.2.0.exe` (~2MB)
2. They run it
3. Installer downloads Electron (~65MB) automatically
4. Installer downloads your app files (~2MB) automatically
5. App is installed and ready!

---

## For Updates

When you push updates:

1. Update `version.json` with new version number
2. Run `package-app-files.bat` again
3. Update the version in `bootstrap-installer.nsi`
4. Compile new installer
5. Create new GitHub Release with both files

Users click "Check Updates" in the app → sees new version → downloads new installer.

---

## File Sizes

| File | Size |
|------|------|
| AETHER-OS-Setup.exe (bootstrap) | ~2 MB |
| aether-os-app-files.zip | ~2 MB |
| Electron (downloaded at install) | ~65 MB |
| **Total user downloads** | **~70 MB** (same as bundled, but split) |

The advantage: Your GitHub release page only needs ~4MB of storage per version instead of ~70MB.
