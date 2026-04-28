# Zephyr Tools

Unified tooling for Zephyr RTOS based embedded projects, supporting CLI, TUI, Desktop, and Web frontends from a single Python core.

## Architecture

```
CLI  --> ZephyrToolsCore
TUI  --> ZephyrToolsCore
Web  --> Local API --> ZephyrToolsCore
Desktop --> Local API --> ZephyrToolsCore
```

All heavy logic (workspace, project, build, flash, monitor, doctor, codegen) lives in `zephyr_tools/core/` and is consumed by frontends via the programmable `ZephyrToolsClient` or the local HTTP API.

## Install

### macOS / Linux

```bash
git clone git@github.com:overrize/zephyr_tools.git
cd zephyr_tools
pip install -e ".[llm]"
zt --version
```

### Windows

If `zt` is not recognized after `pip install`, the Python user `Scripts` folder is not on your `PATH`.

Use the provided install script (it installs the package and adds the Scripts directory to your user PATH automatically):

```powershell
git clone git@github.com:overrize/zephyr_tools.git
cd zephyr_tools
.\install.ps1
```

Then **restart your terminal** and run:

```powershell
zt --version
```

If you prefer manual installation:

```powershell
pip install -e ".[llm]"
```

If `zt` is still not found, add this directory to your user `PATH` manually (replace `3xx` with your Python version):

```
%APPDATA%\Python\Python3xx\Scripts
```

## CLI (`zt`)

```bash
zt doctor                     # Check Zephyr environment
zt init                       # Initialize west workspace
zt boards [filter]            # List Zephyr boards
zt create <name>              # Create a Zephyr app
zt build <project>            # west build
zt flash [-d build]           # west flash
zt monitor [-d build]         # Connect to logs
zt shell [-d build]           # Connect to Zephyr shell
zt gen "<prompt>"             # LLM generate app code
zt fix <project> <prompt>     # LLM fix build errors
zt tui                        # Launch text UI
zt repl                       # Launch interactive REPL (like Claude Code)
zt api                        # Start local API server
```

Global flags:
- `-C, --work-dir`  Working directory (default: cwd)
- `-b, --board`      Default board (default: nucleo_f411re)

## TUI

```bash
zt tui
```

A simple interactive menu for doctor, boards, create, build, flash, and monitor.

## Local API

```bash
zt api [--host 127.0.0.1] [--port 8765]
```

HTTP endpoints:
- `GET  /health`
- `GET  /doctor`
- `GET  /boards?filter=`
- `POST /projects`
- `POST /build`
- `POST /flash`
- `POST /generate`
- `POST /fix`

CORS is enabled for `http://localhost:5173`.

## Web Frontend

```bash
cd apps/web
npm install
npm run dev      # http://localhost:5173
```

The web UI connects to the local API server at `http://127.0.0.1:8765`. Make sure `zt api` is running first.

## Desktop App (Tauri)

Prerequisites: [Rust](https://rustup.rs/)

```bash
cd apps/desktop
cargo tauri dev     # Development
cargo tauri build   # Release
```

The desktop shell embeds the web frontend. Build the web assets first:

```bash
cd apps/web
npm run build
cd ../desktop
cargo tauri build
```

## Project Layout

```
zephyr_tools/
  zephyr_tools/        # Python package
    core/              # Workspace, project, build, flash, monitor, doctor, boards, codegen
    api/               # Local HTTP API server
    llm/               # OpenAI-compatible code generation
    cli.py             # CLI entry
    client.py          # Shared facade
    tui.py             # Terminal UI
  apps/
    web/               # React + Vite + TypeScript
    desktop/           # Tauri (Rust)
  tests/
  docs/
```

## License

MIT
