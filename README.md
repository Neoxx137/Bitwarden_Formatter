# Bitwarden Formatter CLI

Convert Bitwarden’s JSON export into a clean PDF summary.  
Each row shows the entry name, optional folder/type tags, username or email, password, URLs, and TOTP info.

---

## Requirements

- Python 3.10 or newer (Windows, macOS, or Linux)
- Unencrypted Bitwarden JSON export (`Tools → Export → .json`)

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
