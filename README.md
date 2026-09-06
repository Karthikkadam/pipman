# 📦 PipMan (v2.4) — Modern Python Package Manager for Windows

<p align="center">
  <img src="https://img.shields.io/badge/Release-v2.4-10b981?style=for-the-badge&logo=python&logoColor=white" alt="Version 2.4" />
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-38bdf8?style=for-the-badge&logo=windows&logoColor=white" alt="Windows 10/11" />
  <img src="https://img.shields.io/badge/Python-3.8%2B-facc15?style=for-the-badge&logo=python&logoColor=black" alt="Python 3.8+" />
  <img src="https://img.shields.io/badge/License-MIT-2ee59d?style=for-the-badge" alt="License MIT" />
</p>

A sleek, modern visual desktop GUI for managing `pip` packages on Windows. Inspect on-disk package footprint in real-time, search instantly across hundreds of libraries, and execute asynchronous updates or uninstalls with a live streaming terminal.

---

## 🌟 Key Features

- ⚡ **Zero Setup & Standalone**: Portable `.exe` executable with zero external GUI dependencies required.
- 🎨 **Dark Emerald Cyber Aesthetic**: Custom modern UI with high-DPI scaling, neon mint accents (`#10b981`), and sleek card rows.
- 🔍 **Instant Search & Multi-Sort**: Real-time package filtering combined with multi-column sorting (Size, Installed Date, Name, Current/Latest Version).
- 📊 **Accurate Disk Space Inspector**: Calculates exact real-world disk footprint in **MB** and **KB** across metadata `RECORD` files and `site-packages` directories.
- 🖥️ **Live Asynchronous Log Terminal**: Embedded non-blocking terminal displaying real-time `stdout` and `stderr` command outputs without freezing the interface.
- 🔄 **1-Click Updates & Safe Uninstall**: Upgrade packages with PyPI checks and remove packages safely with confirmation dialogues.
- 🌐 **Universal Windows Auto-Detection**: Dynamically discovers virtual environments (`venv`), Conda (`CONDA_PREFIX`), Windows Registry installations, and custom Python paths on any PC.

---

## 🚀 Getting Started

### 1. Run the Python Script Directly
```bash
python "pip manager.py"
```

### 2. Standalone Executable (.exe)
You can launch the pre-compiled executable directly without opening a terminal:
- **Single-File Portable**: `dist/PipMan_Standalone.exe`
- **Instant-Start Folder Edition**: `dist/PipMan/PipMan.exe`

---

## 🛠️ Building from Source

To compile your own standalone Windows executable:

### Using the 1-Click Batch Script:
Double-click `build_exe.bat`.

### Or via Command Line:
```powershell
# Folder distribution (Instant launch, zero runtime extraction)
pyinstaller -y --noconsole --onedir --name "PipMan" --clean --noupx "pip manager.py"

# Single-file portable standalone
pyinstaller -y --noconsole --onefile --noupx --clean --paths "C:\Python313\DLLs" --name "PipMan_Standalone" "pip manager.py"
```

---

## 📁 Project Structure

```text
├── pip manager.py            # Main application source code
├── build_exe.bat             # 1-click PyInstaller build script
├── dist/                     # Compiled executables
│   ├── PipMan/               # Folder distribution (PipMan.exe)
│   └── PipMan_Standalone.exe # Single-file standalone executable
├── website/                  # Product landing page & download portal
│   ├── index.html            # Landing page with interactive live simulator
│   ├── style.css             # Cyber emerald design system
│   ├── script.js             # Interactive simulator logic
│   └── downloads/            # Downloadable standalone binaries
├── .gitignore                # Git ignore rules
├── LICENSE                   # MIT License
└── README.md                 # Project documentation
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE) — free and open for personal and commercial use.
