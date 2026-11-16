"""Write the copy sheets for the submission form from docs/project-page.md.

The Space Apps project form takes each answer in its own box, and its two link lists take one
name and one address per row. This script reads the answers from docs/project-page.md ("The
form, field by field") and writes them out so that each value can be copied by itself:

  docs/form-copy-sheet.md    every value in its own code block (GitHub puts a copy button on each)
  docs/form-copy-sheet.html  one page with a copy button on every value; open the file in a browser

Run it again after changing docs/project-page.md:

    python scripts/make_form_copy_sheet.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "project-page.md"
TEMPLATE = ROOT / "scripts" / "form_copy_sheet.template.html"
OUT_MD = ROOT / "docs" / "form-copy-sheet.md"
OUT_HTML = ROOT / "docs" / "form-copy-sheet.html"

SITE = "https://spherex-sky-change-viewer.onrender.com"
REPO = "https://github.com/tatsatshah05/Ampersand-NASA"

# What a person should know about an address that our own check could not open.
NOT_OPENED = "Our automated check does not open this site. Open it once yourself to confirm it."
ROW_NOTES = {
    "https://ui.adsabs.harvard.edu": NOT_OPENED,
    "https://www.astronomerstelegram.org": NOT_OPENED,
    "https://www.aavso.org/vsx/index.php": "This site refused our automated check. Open it once yourself to confirm.",
    "https://simbad.harvard.edu/simbad/": "The Harvard mirror: the Strasbourg original was down on 15 November.",
}


def between(text: str, start: str, end: str) -> str:
    i = text.index(start) + len(start)
    return text[i : text.index(end, i)]


def link_rows(section: str) -> list[dict[str, str]]:
    rows = []
    for line in section.splitlines():
        if not line.startswith("| ") or line.startswith("| Link Text") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        if len(cells) != 2 or not cells[1].startswith("http"):
            raise SystemExit(f"Not a row of name and address: {line}")
        row = {"text": cells[0], "url": cells[1]}
        if cells[1] in ROW_NOTES:
            row["note"] = ROW_NOTES[cells[1]]
        rows.append(row)
    return rows


def read_answers() -> dict:
    text = SOURCE.read_text()
    name = between(text, "## 1. Project Name\n", "## 2.").strip()
    paragraphs = [p.strip() for p in between(text, "## 2. High-Level Project Summary\n", "## 3.").split("\n\n")]
    paragraphs = [p for p in paragraphs if p]
    if not paragraphs[0].startswith("The form's box takes"):
        raise SystemExit("The summary's first paragraph should be the note about the box's limit.")
    summary = "\n\n".join(paragraphs[1:])
    if len(summary) > 1500:
        raise SystemExit(f"The summary is {len(summary)} characters; the form's box takes 1,500.")
    if SITE not in between(text, "## 4. Link to Final Project\n", "## 5."):
        raise SystemExit("The site's address is not in field 4.")
    details = text[text.index("WHAT IT DOES\n") : text.index("## 6. Use of Super Intelligence")].rstrip()
    nasa = link_rows(between(text, "## 7. NASA Data\n", "## 8."))
    other = link_rows(between(text, "## 8. Space Agency Partner Data and Other References\n", "# Longer text"))
    fields = [
        {
            "id": "name",
            "label": "Project Name",
            "value": name,
            "note": "The site's top bar says Ampersand. Change this name if you want the two to match.",
        },
        {
            "id": "summary",
            "label": "Summary",
            "value": summary,
            "meta": f"{len(summary):,} of 1,500 characters, {len(summary.split())} words",
        },
        {
            "id": "demo",
            "label": "Project Demo (link)",
            "noteLead": "Not ready.",
            "note": "Upload the 7-slide deck, or a video of 30 seconds or less, to a public link that needs no "
            "sign-in. Then paste that link in the form.",
        },
        {
            "id": "project",
            "label": "Project (link)",
            "value": SITE,
            "url": True,
            "note": "The box takes one link. Keep the website here: the GitHub link goes in Project Details and in "
            "the second link list.",
        },
        {
            "id": "github",
            "label": "GitHub link",
            "value": REPO,
            "url": True,
            "note": "Already inside Project Details and the first row of Partner & Other Data. Here for anywhere "
            "else you want it.",
        },
        {
            "id": "details",
            "label": "Project Details",
            "value": details,
            "long": True,
            "meta": f"{len(details):,} characters, {len(details.split()):,} words",
            "noteLead": "Confirm one sentence before pasting.",
            "note": 'In USE OF AI: "AI agents also proposed and built the methods of the extra searches that we '
            'asked for". Correct it if that is not how it went.',
        },
        {
            "id": "si",
            "label": "Use of Super Intelligence (SI)",
            "noteLead": "Options to tick, nothing to paste.",
            "note": "Tick every option that covers writing code, writing or editing text, and analysing data or "
            "research. Tick slides or presentations if AI wrote the deck's words. Do not tick images, video or "
            'audio unless the deck or the video has any. Do not tick "I did not use SI".',
        },
    ]
    return {"fields": fields, "nasa": nasa, "other": other}


def fence(value: str) -> str:
    return f"```text\n{value}\n```\n"


def markdown(data: dict) -> str:
    out = [
        "# Form copy sheet\n",
        "Every answer for the Space Apps project form, each in its own box. On GitHub, point at a box and press "
        "the copy button at its right end, then paste into the form. Made by `scripts/make_form_copy_sheet.py` "
        "from [project-page.md](project-page.md): change that file and run the script, not this one. The same "
        "sheet as one page with a button on every value: [form-copy-sheet.html](form-copy-sheet.html) (download "
        "it and open it in a browser).\n",
        "## Text answers\n",
    ]
    for f in data["fields"]:
        out.append(f"### {f['label']}" + (f" ({f['meta']})" if f.get("meta") else "") + "\n")
        if f.get("value"):
            out.append(fence(f["value"]))
        if f.get("note"):
            lead = f"**{f['noteLead']}** " if f.get("noteLead") else ""
            out.append(f"{lead}{f['note']}\n")
    for title, key in (("NASA Data", "nasa"), ("Space Agency Partner & Other Data", "other")):
        rows = data[key]
        out.append(f"## {title} ({len(rows)} rows)\n")
        out.append('Each row is one "Add New Link": the first box is Link Text, the second is Link Url.\n')
        for i, r in enumerate(rows, 1):
            out.append(f"**{i}.**" + (f" {r['note']}" if r.get("note") else "") + "\n")
            out.append(fence(r["text"]))
            out.append(fence(r["url"]))
    return "\n".join(out)


def html(data: dict) -> str:
    template = TEMPLATE.read_text()
    if template.count("/*__DATA__*/") != 1:
        raise SystemExit("The template should hold the marker /*__DATA__*/ exactly once.")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    head = '<!doctype html>\n<html lang="en">\n<meta charset="utf-8">\n'
    head += '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
    return head + template.replace("/*__DATA__*/", payload) + "</html>\n"


def main() -> None:
    data = read_answers()
    OUT_MD.write_text(markdown(data))
    OUT_HTML.write_text(html(data))
    print(f"{len(data['nasa'])} NASA rows, {len(data['other'])} other rows")
    print(f"wrote {OUT_MD.relative_to(ROOT)} and {OUT_HTML.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
