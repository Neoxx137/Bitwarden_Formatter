#!/usr/bin/env python3
"""Bitwarden JSON export -> polished PDF."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from html import escape
from pathlib import Path
from shutil import which
from typing import Any, Dict, List, Sequence

def base_dir() -> Path:
    """Return the folder that stores templates/styles/fonts (PyInstaller-safe)."""
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


HERE = base_dir()
TEMPLATE_PATH = HERE / "templates" / "layout.html"
STYLE_PATH = HERE / "styles" / "style.css"
BROWSER_ENV_VAR = "BITWARDEN_FORMATTER_BROWSER"

TYPE_NAMES = {
    1: "Login",
    2: "Secure Note",
    3: "Card",
    4: "Identity",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a Bitwarden JSON export into a well-formatted PDF overview."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the Bitwarden JSON export (created via Bitwarden > Export).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional PDF destination. Defaults to the input path with a .pdf extension.",
    )
    parser.add_argument(
        "--title",
        default="Bitwarden Vault Overview",
        help="Title for the PDF cover and metadata.",
    )
    return parser.parse_args()


def load_export(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_output_path(input_path: Path, provided: Path | None) -> Path:
    if provided:
        return provided
    return input_path.with_suffix(".pdf")


def normalize_datetime(value: str | None) -> str:
    if not value:
        return ""
    try:
        clean = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
    except ValueError:
        return value
    return dt.strftime("%m/%d/%Y %I:%M %p")


def collect_accounts(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    folders = {folder.get("id"): folder.get("name", "") for folder in payload.get("folders", [])}
    accounts: List[Dict[str, Any]] = []

    for item in payload.get("items", []):
        login = item.get("login") or {}
        uris = [
            uri.get("uri", "") for uri in login.get("uris", []) if isinstance(uri, dict) and uri.get("uri")
        ]
        custom_fields = []
        for field in item.get("fields") or []:
            name = field.get("name") or "Field"
            value = field.get("value")
            if not value:
                continue
            custom_fields.append(f"{name}: {value}")

        accounts.append(
            {
                "name": item.get("name") or "(untitled)",
                "type": TYPE_NAMES.get(item.get("type"), "Unknown"),
                "folder": folders.get(item.get("folderId")) or "No folder",
                "favorite": bool(item.get("favorite")),
                "username": login.get("username") or "",
                "password": login.get("password") or "",
                "totp": login.get("totp") or "",
                "uris": uris,
                "notes": item.get("notes") or "",
                "last_modified": normalize_datetime(item.get("revisionDate") or item.get("lastRevisionDate")),
                "created": normalize_datetime(item.get("creationDate")),
                "fields": custom_fields,
            }
        )

    accounts.sort(key=lambda entry: (entry["folder"].lower(), entry["name"].lower()))
    return accounts


def render_html(accounts: List[Dict[str, Any]], title: str) -> str:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Missing HTML template: {TEMPLATE_PATH}")
    generated = datetime.now().strftime("%m/%d/%Y %I:%M %p")
    rows_html = build_rows(accounts)
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        "title": escape(title),
        "generated": generated,
        "count": str(len(accounts)),
        "rows": rows_html if rows_html else '<tr><td colspan="2" class="empty">No entries found</td></tr>',
        "style_href": STYLE_PATH.as_uri(),
    }
    for key, value in replacements.items():
        html = html.replace(f"{{{{{key}}}}}", value)
    return html


def build_rows(accounts: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for entry in accounts:
        name = escape(entry["name"] or "(untitled)")
        meta = render_meta(entry)
        credential_block = render_credentials_section(entry)
        parts.append(
            "\n".join(
                [
                    "<tr>",
                    f'  <td><div class="entry-name">{name}</div>{meta}</td>',
                    f"  <td>{credential_block}</td>",
                    "</tr>",
                ]
            )
        )
    return "\n".join(parts)


def render_meta(entry: Dict[str, Any]) -> str:
    tags: List[str] = []
    folder = entry.get("folder")
    if folder and folder.lower() != "no folder":
        tags.append(f'<span class="tag">{escape(folder)}</span>')
    type_name = entry.get("type")
    if type_name:
        tags.append(f'<span class="tag">{escape(type_name)}</span>')
    if entry.get("favorite"):
        tags.append('<span class="tag tag--favorite">Favorite</span>')
    if not tags:
        return '<div class="entry-meta">None</div>'
    return f'<div class="entry-meta">{"".join(tags)}</div>'


def render_credentials_extra(entry: Dict[str, Any]) -> str:
    bits: List[str] = []
    if entry.get("uris"):
        primary = escape(entry["uris"][0])
        bits.append(f'<span>URL: {primary}</span>')
    if entry.get("totp"):
        bits.append(f'<span>2FA: {escape(entry["totp"])}</span>')
    return "\n".join(bits)


def render_credentials_section(entry: Dict[str, Any]) -> str:
    username = escape(entry["username"] or "-")
    password = escape(entry["password"] or "-")
    extras = render_credentials_extra(entry)
    extra_html = f'<div class="credentials-extra">{extras}</div>' if extras else ""
    return "\n".join(
        [
            '<div class="credentials">',
            '  <div class="credential-block credential-block--user">',
            '    <span class="credential-label">Username / Email</span>',
            f'    <span class="credential-value">{username}</span>',
            "  </div>",
            '  <div class="credential-block credential-block--password">',
            '    <span class="credential-label">Password</span>',
            f'    <span class="credential-value">{password}</span>',
            "  </div>",
            f"  {extra_html}",
            "</div>",
        ]
    )


def build_pdf(accounts: List[Dict[str, Any]], title: str, output: Path) -> None:
    if not STYLE_PATH.exists():
        raise FileNotFoundError(f"Missing CSS file: {STYLE_PATH}")
    output.parent.mkdir(parents=True, exist_ok=True)
    pdf_target = output.resolve()
    html_content = render_html(accounts, title)
    html_path = pdf_target.with_suffix(".html")
    html_path.write_text(html_content, encoding="utf-8")
    browser = find_browser_binary()
    run_headless_browser(browser, html_path, pdf_target)


def find_browser_binary() -> Path:
    env_browser = os.environ.get(BROWSER_ENV_VAR)
    if env_browser:
        expanded = Path(env_browser).expanduser()
        if expanded.exists():
            return expanded

    candidates: List[Path] = []

    def add_candidate(path_like: str | Path | None) -> None:
        if not path_like:
            return
        candidate = Path(path_like)
        if candidate.exists():
            candidates.append(candidate)

    system = platform.system().lower()

    if system == "windows":
        program_files = [
            Path(os_path)
            for os_path in {
                os.environ.get("PROGRAMFILES"),
                os.environ.get("PROGRAMFILES(X86)"),
                os.environ.get("LOCALAPPDATA"),
            }
            if os_path
        ]
        known_suffixes = [
            ("Microsoft", "Edge", "Application", "msedge.exe"),
            ("Microsoft", "Edge SxS", "Application", "msedge.exe"),
            ("Google", "Chrome", "Application", "chrome.exe"),
            ("Chromium", "Application", "chrome.exe"),
        ]
        for base in program_files:
            for suffix in known_suffixes:
                add_candidate(base.joinpath(*suffix))
    elif system == "darwin":
        mac_candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ]
        for path in mac_candidates:
            add_candidate(path)
    else:  # Linux / other Unix
        linux_candidates = [
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
            "/usr/bin/microsoft-edge",
            "/snap/bin/chromium",
            "/usr/bin/brave-browser",
        ]
        for path in linux_candidates:
            add_candidate(path)

    which_names = (
        "msedge",
        "microsoft-edge",
        "chrome",
        "google-chrome-stable",
        "google-chrome",
        "chromium-browser",
        "chromium",
        "brave-browser",
    )
    which_candidates = [which(name) for name in which_names]
    candidates.extend(Path(path) for path in which_candidates if path)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "No supported headless browser found. Install Edge/Chrome/Chromium or set "
        f"{BROWSER_ENV_VAR} to a custom binary."
    )


def run_headless_browser(browser: Path, html_path: Path, output: Path) -> None:
    commands: Sequence[Sequence[str]] = [
        (
            str(browser),
            "--headless=new",
            "--disable-gpu",
            f"--print-to-pdf={output}",
            "--print-to-pdf-no-header",
            html_path.as_uri(),
        ),
        (
            str(browser),
            "--headless",
            "--disable-gpu",
            f"--print-to-pdf={output}",
            "--print-to-pdf-no-header",
            html_path.as_uri(),
        ),
    ]
    last_error: subprocess.CalledProcessError | None = None
    for cmd in commands:
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return
        except subprocess.CalledProcessError as error:
            last_error = error
    raise RuntimeError(
        f"Headless browser failed to create the PDF. Output: {last_error.stderr.decode('utf-8', errors='ignore') if last_error else 'unknown'}"
    )


def main() -> None:
    args = parse_args()
    input_path: Path = args.input.expanduser()
    output_path = resolve_output_path(input_path, args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    data = load_export(input_path)
    accounts = collect_accounts(data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    build_pdf(accounts, args.title, output_path)
    print(f"PDF created successfully: {output_path}")


if __name__ == "__main__":
    main()
