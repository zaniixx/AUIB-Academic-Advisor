"""Turn AUIB's released curriculum documents into plain text that build.py reads.

The documents sit in ``sis_data/released doc`` (kept out of git with the rest of sis_data). PDFs
are converted with ``pdftotext`` from Poppler, Word files with the standard library, and the
text lands in ``sis_data/released doc/.extracted``.
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET  # noqa: S405 - the documents are AUIB's own Word files

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "sis_data" / "released doc"
WORK = SOURCE / ".extracted"
RAW = WORK / "raw"  # PDFs in reading order, one paragraph per line
TEXT = WORK / "text"  # Word files: paragraphs, and table rows as cells joined by " | "

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _text_of(node: ET.Element) -> str:
    parts = []
    for element in node.iter():
        if element.tag == W + "t" and element.text:
            parts.append(element.text)
        elif element.tag in (W + "tab", W + "br", W + "cr"):
            parts.append(" ")
    return "".join(parts).strip()


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))  # noqa: S314 - AUIB's own document
    body = root.find(W + "body")
    lines: list[str] = []
    for child in body if body is not None else ():
        if child.tag == W + "p" and (line := _text_of(child)):
            lines.append(line)
        elif child.tag == W + "tbl":
            for row in child.iter(W + "tr"):
                cells = [_text_of(cell) for cell in row.findall(W + "tc")]
                if any(cells):
                    lines.append(" | ".join(cells))
    return "\n".join(lines)


def run() -> None:
    if not SOURCE.is_dir():
        raise SystemExit(f"Put the released curriculum documents in {SOURCE}")
    pdftotext = shutil.which("pdftotext")
    if pdftotext is None:
        raise SystemExit("pdftotext (Poppler) is needed to read the PDF curricula")
    RAW.mkdir(parents=True, exist_ok=True)
    TEXT.mkdir(parents=True, exist_ok=True)
    for pdf in SOURCE.rglob("*.pdf"):
        if "__MACOSX" in pdf.parts:
            continue
        out = RAW / (pdf.stem.replace(" ", "_") + ".txt")
        subprocess.run([pdftotext, str(pdf), str(out)], check=True)  # noqa: S603 - fixed arguments
    for docx in SOURCE.rglob("*.docx"):
        name = docx.stem
        if "Track" in name:  # "Degree Plan - ACC Track - 20241110" -> BUS-ACC
            name = "BUS-" + name.split(" - ")[1].split()[0]
        elif name.startswith("CIS"):
            name = "CIS"
        (TEXT / f"{name}.txt").write_text(docx_text(docx), encoding="utf-8")


if __name__ == "__main__":
    run()
