# Bitwarden Formatter CLI

Convert Bitwarden’s JSON export into a clean PDF summary.  
Each row shows the entry name, optional folder/type tags, username or email, password, URLs, and TOTP info.  
The script renders HTML/CSS and prints it to PDF through a Chromium-based browser (Edge/Chrome/Chromium/Brave).

---

## Requirements

- Python 3.10 or newer (Windows, macOS, or Linux)
- A Chromium browser installed locally (Edge, Chrome, Chromium, or Brave)
- Unencrypted Bitwarden JSON export (`Tools → Export → .json`)
- Optional: set `BITWARDEN_FORMATTER_BROWSER=/path/to/browser` if auto-detection fails

---

## Usage

```bash
python main.py /path/to/bitwarden_export.json
# custom output path / title
python main.py /path/to/export.json -o outputs/vault.pdf --title "Family Vault"
```

The script writes a `.pdf` and a sibling `.html` file. The HTML copy is useful for inspecting or restyling the output; delete it if you do not need it.

Long passwords and URLs wrap automatically so nothing is truncated inside the PDF.

---

## PyInstaller (optional single-file binary)

```bash
pip install pyinstaller
pyinstaller --onefile --noconfirm --name bitwarden_formatter \
  --add-data "templates:templates" \
  --add-data "styles:styles" \
  --add-data "fonts:fonts" \
  main.py
```

Windows PowerShell syntax (using `;` as the data separator) or reuse the included `bitwarden_formatter.spec`:

```powershell
pyinstaller bitwarden_formatter.spec
# or
pyinstaller --onefile --noconfirm --name bitwarden_formatter `
  --add-data "templates;templates" `
  --add-data "styles;styles" `
  --add-data "fonts;fonts" `
  main.py
```

Run the generated `bitwarden_formatter.exe` from a terminal and pass the JSON path, e.g.:

```powershell
cd dist
.\bitwarden_formatter.exe C:\Users\you\Downloads\bitwarden_export.json
```

Launching the exe without arguments will immediately print the standard usage message and exit.

---

## Project Layout

- `main.py` – CLI entry point; parses JSON, builds HTML, prints PDF via headless browser
- `templates/layout.html` – structure of the hero header + table
- `styles/style.css` – typography, colors, and print rules (usage of overflow-wrap ensures long values stay visible)
- `fonts/` – optional font files for custom builds
- `bitwarden_formatter.spec` – ready-to-use PyInstaller spec
- `requirements.txt` – reminder that the Python standard library is sufficient

---

## Security Note

Both the JSON export and the produced PDF/HTML contain passwords in plain text. Handle them only on trusted systems and delete or secure the files once you are done.
