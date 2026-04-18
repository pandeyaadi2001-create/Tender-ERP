# Windows Build Guide for Tender ERP

## Quick Build (One Command)

Double-click `build_windows.bat` or run in Command Prompt:

```cmd
build_windows.bat
```

This will:
1. Create a Python virtual environment
2. Install all dependencies
3. Run tests
4. Build `TenderERP.exe` via PyInstaller
5. Create `TenderERP-Setup.exe` installer (if Inno Setup is installed)
6. Create `TenderERP-Windows.zip` for distribution

---

## Manual Build Steps

### Prerequisites
- **Python 3.11+**: [Download](https://www.python.org/downloads/)
  - ☑️ Check "Add Python to PATH" during install
- **Inno Setup 6** (optional, for installer): [Download](https://jrsoftware.org/isinfo.php)

### Step-by-step

```cmd
# 1. Clone the repo
git clone https://github.com/pandeyaadi2001-create/Tender-ERP.git
cd Tender-ERP

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
pip install pyinstaller

# 4. Build the executable
pyinstaller --noconfirm --clean tender_erp_win.spec

# 5. Test it
dist\TenderERP\TenderERP.exe

# 6. (Optional) Build the installer
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

---

## Output Files

| File | Location | Description |
|------|----------|-------------|
| Standalone EXE | `dist\TenderERP\TenderERP.exe` | Run directly (needs the whole folder) |
| Portable ZIP | `dist\TenderERP-Windows.zip` | Share as zip, extract and run |
| Installer | `Output\TenderERP-Setup.exe` | Proper Windows installer with Start Menu, Desktop shortcut |

---

## CI/CD (Automatic Builds)

Push to GitHub → Actions automatically builds both Windows `.exe` and macOS `.dmg`.
Download from: **Actions** → **Build & Test** → **Artifacts** section.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `python` not found | Install Python 3.11+ and check "Add to PATH" |
| PyInstaller fails | Try `pip install --upgrade pyinstaller` |
| DLL errors on launch | Install [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) |
| App icon missing | Place your `.ico` file at `assets/icon.ico` |
