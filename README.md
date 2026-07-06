# L.E.A.D.

L.E.A.D. is an electronics inventory application with DigiKey lookup, BOM workflows, barcode scanning, and LED-guided part location.

The current desktop app is built with `PyQt6`. The older Tkinter UI is no longer the active frontend.

## Current Features

- DigiKey part lookup
- Manual part entry and editing
- Part detail popup with checkout and highlight actions
- Barcode scan and bulk scan flows
- BOM import, preview, check-in, and checkout
- LED-guided location highlighting for single parts and BOM checkout
- Low-stock export
- In-app settings for DigiKey, serial, and file paths
- Test mode support
- Configurable active LED count for the Arduino strip controller
- In-app Git-based update check

## Project Layout

- [main.py](/c:/Users/ginoc/OneDrive/Desktop/L.E.A.D/main.py): Qt application entrypoint
- [frontend.py](/c:/Users/ginoc/OneDrive/Desktop/L.E.A.D/frontend.py): Qt UI
- [backend.py](/c:/Users/ginoc/OneDrive/Desktop/L.E.A.D/backend.py): inventory and BOM logic
- [digikey_api_local.py](/c:/Users/ginoc/OneDrive/Desktop/L.E.A.D/digikey_api_local.py): DigiKey API client
- [ledSerial.py](/c:/Users/ginoc/OneDrive/Desktop/L.E.A.D/ledSerial.py): serial LED controller
- [arduino/lead_led_controller/lead_led_controller.ino](/c:/Users/ginoc/OneDrive/Desktop/L.E.A.D/arduino/lead_led_controller/lead_led_controller.ino): Arduino firmware for the LED strip controller
- [file_initializer.py](/c:/Users/ginoc/OneDrive/Desktop/L.E.A.D/file_initializer.py): config and runtime file setup
- [image_cache.py](/c:/Users/ginoc/OneDrive/Desktop/L.E.A.D/image_cache.py): cached DigiKey image storage

## Requirements

- Python 3.10+
- Dependencies from `requirements.txt`

Install dependencies:

```powershell
pip install -r requirements.txt
```

## Running

```powershell
python main.py
```

On first startup the app creates its runtime files under `Databases/` if they do not already exist, then opens the settings dialog so you can fill in configuration values.

## Configuration

Use the gear button in the app sidebar to edit configuration.

The Settings dialog also includes `Check for Updates`, which runs [check_for_updates.bat](/c:/Users/ginoc/OneDrive/Desktop/L.E.A.D/check_for_updates.bat) from the repo root. The updater:

- fetches the current branch from `origin`
- fast-forwards only when the tracked worktree is clean
- leaves ignored runtime folders such as `Databases/` and `backups/` alone

After a successful update, restart the application so the new code is loaded.

Config sections:

- `API`
  - `DIGIKEY_CLIENT_ID`
  - `DIGIKEY_CLIENT_SECRET`
- `SERIAL`
  - `PORT`
  - `BAUDRATE`
  - `TIMEOUT`
  - `LED_COUNT`
- `FILES`
  - `COMPONENT_CATALOGUE`
  - `CHANGELOG`
  - `IMAGE_CACHE`

Blank file paths fall back to the default files under `Databases/`.

For LED hardware:

- `LED_COUNT` controls how many LEDs the desktop app actively manages.
- The bundled Arduino sketch supports up to `260` LEDs and persists the active count set by the app.
- If `LED_COUNT` is left blank, the app defaults to `104`.

## Notes

- If the LED hardware is disconnected, the app should stay usable and report that state in the UI instead of crashing.
- DigiKey image responses are cached in a local SQLite database.
- Runtime data under `Databases/` is ignored by git.
