# Zephyr Tools Desktop

Tauri-based desktop shell for Zephyr Tools.

## Prerequisites

- [Rust](https://rustup.rs/)
- [Node.js](https://nodejs.org/)
- Python environment with `zephyr-tools` installed and `zt api` available

## Development

Start the web frontend dev server first:

```bash
cd ../web
npm run dev
```

Then run the Tauri app in another terminal:

```bash
cd apps/desktop
cargo tauri dev
```

## Build

Build the production web assets:

```bash
cd ../web
npm run build
```

Build the desktop app:

```bash
cd apps/desktop
cargo tauri build
```

## Notes

- The desktop app embeds the web UI from `../web/dist`.
- Make sure the Python API server (`zt api`) is running before using features that call the backend.
- Alternatively, the desktop app can be extended to auto-launch the Python API on startup.
