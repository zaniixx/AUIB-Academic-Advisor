"""Pull course descriptions (code, title, credits, text) out of the released curriculum PDFs."""
import json
import re

from extract import RAW, WORK

SOURCES = {
    "COD": "Academic-Curriculum-COD-for-website",
    "COP": "Academic-Curriculum-COP-for-website",
    "OVS": "Appendix_II_CoursesDescription_for_Optometry_and_Vision_Science",
    "RAD": "Appendix_IV__Course_descriptions_for_Radiologic_and_Sonal_Sciences",
    "BDT": "Appendix_VI_for_Dental_Technology",
    "ANT": "Appendix_VIII__Course_descriptions_for_anesthesia_technology",
}

CODE = r"(?P<code>(?:[A-Z]{3,4})\s?\d{3}[A-Z]?(?:\s?L)?)"
ENTRY = re.compile(
    CODE
    + r"\s*[:\-–—�]?\s*"
    + r"(?P<title>[A-Za-z&/,'’().:\- ]{3,120}?)\s*"
    + r"\(?(?P<cr>\d+(?:\.\d+)?)\s*(?:Credits?|credits?|cr\b|Cr\b|CR\b)\)?"
)
FOOTER = re.compile(r"COD Curriculum \d+|^\s*\d+\s*$", re.M)


def normalise_code(code: str) -> str:
    code = re.sub(r"\s+", "", code)
    match = re.match(r"([A-Z]{3,4})(\d{3}[A-Z]?)", code)
    return f"{match.group(1)} {match.group(2)}" if match else code


def parse(name: str) -> dict[str, dict]:
    text = (RAW / f"{name}.txt").read_text(encoding="utf-8", errors="replace")
    text = FOOTER.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    found: dict[str, dict] = {}
    matches = list(ENTRY.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        code = normalise_code(m.group("code"))
        body = text[m.end() : end].strip()
        entry = {"title": m.group("title").strip(" -:"), "credits": float(m.group("cr")), "text": body}
        if code not in found or len(body) > len(found[code]["text"]):
            found[code] = entry
    return found


def run() -> None:
    out = {key: parse(name) for key, name in SOURCES.items()}
    (WORK / "descriptions.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    run()
