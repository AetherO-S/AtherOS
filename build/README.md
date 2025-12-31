# Build Resources

This folder contains resources for building the installer.

## Required Files

### icon.ico (Windows)
- Required for Windows build
- Must contain multiple sizes: 16, 32, 48, 64, 128, 256 pixels
- Create from `icon.svg` using https://icoconvert.com

### icon.icns (Mac)
- Required for Mac build
- Create from PNG using https://cloudconvert.com/png-to-icns

### icons/ folder (Linux)
- Create PNG files at sizes: 16, 32, 48, 64, 128, 256, 512
- Name format: `16x16.png`, `32x32.png`, etc.

### installerSidebar.bmp (Optional)
- Windows installer sidebar image
- Size: 164x314 pixels
- 24-bit BMP format

## Quick Start

1. Open `icon.svg` in a browser
2. Screenshot or export as 512x512 PNG
3. Convert to ICO at https://icoconvert.com
4. Save as `icon.ico` in this folder

Then run:
```bash
npm run build
```
