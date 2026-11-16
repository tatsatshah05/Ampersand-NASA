"""The Astronomer's Telegram, searched for an earlier report of Candidates A, B and C.

Reading only: it posts the site's own archive search form and opens telegrams one at a time, a few
seconds apart. Nothing is submitted. (The site's robots.txt allows automated reading.)

    python scripts/atel_check.py form   <cache dir>   the keyword searches of the checklist
    python scripts/atel_check.py read   <cache dir> <number> ...   open these telegrams, slowly
    python scripts/atel_check.py report <cache dir>   positions in the texts read against A, B, C

It cannot read every telegram: on 2026-11-16 the site showed "Please confirm you are not a robot. You have read
many Telegrams" at the sixth page read in a row. That check is not answered; `read` stops at it.

The telegrams' texts stay in <cache dir> (they are their authors'); what is kept in the repository is
docs/sweep/vetting/checks_2026-11-16/: the log of requests and what was found.
The checklist: docs/sweep/searches-for-earlier-reports.md, section (d), step 1.
"""
from __future__ import annotations

import html
import json
import math
import re
import sys
import time
from pathlib import Path

import requests

SITE = "https://www.astronomerstelegram.org"
UA = "Mozilla/5.0 (compatible; reading-script)"
OUT = Path(__file__).resolve().parent.parent / "docs" / "sweep" / "vetting" / "checks_2026-11-16"
SINCE = (2025, 8, 1)  # all three were still absent in August 2025
PAUSE = 40.0  # between telegram pages; the search form's requests are 6 s apart

CANDIDATES = {"A": (270.80408, -23.46818), "B": (253.18038, -44.67697), "C": (241.70906, -52.20564)}
# The checklist's words, and the ruling's own ("Also, from the ruling's own lists").
WORDS = ["V7994", "SPHEREx", "Sagittarius", "Sgr", "18:03", "18 03", "Scorpius", "Sco", "16:52", "16 52", "Seach",
         "Norma", "Nor", "16:06", "16 06", "infrared", "Ara", "nova"]
MONTHS = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


def text_of(page: str) -> str:
    page = re.sub(r"<(script|style).*?</\1>", " ", page, flags=re.S | re.I)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


def is_robot_check(page: str) -> bool:
    """The site's "please confirm you are not a robot" page. (Every page loads the reCAPTCHA script for the
    posting form, so the word "captcha" alone says nothing.)"""
    return bool(re.search(r"not a robot|are you (a )?human", text_of(page), re.I))


def site_count(page: str) -> int | None:
    """The site's own "N Selected of M Telegrams"."""
    m = re.search(r"(\d+) Selected of \d+ Telegrams", page)
    return int(m[1]) if m else None


def listed(page: str) -> list[dict]:
    """The telegrams a results page lists: number, title, date."""
    rows = []
    row = r'class="num"\s*>\s*(\d+)\s*</TD>.*?\?read=\d+">(.*?)</A>.*?<EM>\s*(\d{1,2}) (\w{3}) (\d{4});'
    for m in re.finditer(row, page, re.S):
        rows.append({"n": int(m[1]), "title": text_of(m[2]), "date": f"{m[5]}-{MONTHS[m[4]]:02d}-{int(m[3]):02d}"})
    return rows


def archive(s: requests.Session, keywords: str = "") -> tuple[int, str]:
    data = {"ListCriteria": "Archive", "StartMonth": "Jun", "StartYear": "2025", "EndMonth": "Dec", "EndYear": "2026",
            "KeySearch": "Yes" if keywords else "No", "Keywords": keywords, "Author": ""}
    if keywords:
        data["Boolean"] = "Any"
    r = s.post(SITE, data=data, timeout=60)
    return r.status_code, r.text


def form(cache: Path) -> None:
    s = session()
    status, page = archive(s)
    index = listed(page)
    (cache / "index.json").write_text(json.dumps(index))
    print(f"index: HTTP {status}, {len(index)} telegrams, {index[-1]['n']} to {index[0]['n']} ({index[0]['date']})")
    out = [{"word": "(index, no keyword)", "utc": now(), "status": status, "n": len(index),
            "first": index[-1]["n"], "last": index[0]["n"], "last_date": index[0]["date"]}]
    for word in WORDS:
        time.sleep(6)
        utc = now()
        status, page = archive(s, word)
        rows = listed(page)
        entry = {"word": word, "utc": utc, "status": status, "robot_check": is_robot_check(page), "n": len(rows),
                 "site_says": site_count(page)}
        if len(rows) <= 60:
            entry["telegrams"] = [{"n": r["n"], "date": r["date"], "title": r["title"]} for r in rows]
        out.append(entry)
        print(f"{utc}  {word!r}: HTTP {status}, {len(rows)} telegrams (the site says {entry['site_says']})",
              "ROBOT CHECK" if entry["robot_check"] else "", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "form_searches.json").write_text(json.dumps(out, indent=1) + "\n")


def read(cache: Path, numbers: list[int]) -> None:
    """Open the given telegrams one at a time, slowly, and keep their text. Stops for good at the site's
    "please confirm you are not a robot" page (it showed that page at the sixth telegram read in a row, a few
    seconds apart, on 2026-11-16): the check is never answered and never waited out."""
    pages = cache / "pages"
    pages.mkdir(exist_ok=True)
    s = session()
    log = (cache / "scan.log").open("a")
    for n in numbers:
        file = pages / f"{n}.txt"
        if file.exists() and file.stat().st_size > 300:
            continue
        try:
            r = s.get(f"{SITE}/?read={n}", timeout=60)
            status, txt = r.status_code, text_of(r.text)
        except requests.RequestException as e:
            status, txt = 0, repr(e)
        i = txt.find(f"ATel #{n}")
        if status != 200 or i < 0 or is_robot_check(txt):
            log.write(json.dumps({"n": n, "utc": now(), "status": status, "refused": True, "said": txt[:300]}) + "\n")
            log.flush()
            print(f"stopped at {n}: HTTP {status}: {txt[:160]!r}", flush=True)
            return
        file.write_text(txt[i:])
        log.write(json.dumps({"n": n, "utc": now(), "status": status, "chars": len(txt)}) + "\n")
        log.flush()
        print(f"{now()}  {n}: read, {len(txt)} characters", flush=True)
        time.sleep(PAUSE)
    print("done", flush=True)


# ---- positions in a text ----

SIGN = r"([+\-−–])"
SEXA = re.compile(
    r"(?<![\d.])([012]?\d)\s*(?:h|hr|:|\s)\s*([0-5]\d)\s*(?:m|min|:|\s|')\s*([0-5]\d(?:\.\d+)?)\s*(?:s|sec|\"|'')?"
    r"(.{0,60}?)" + SIGN + r"\s*(\d{1,2})\s*(?:d|deg|°|:|\s)\s*([0-5]\d)\s*(?:m|'|′|:|\s)\s*([0-5]\d(?:\.\d+)?)", re.S)
DECIMAL = re.compile(r"(?<![\d.])(\d{1,3}\.\d{2,})\s*(?:deg|°|d)?\s*(?:,|;|\s|and)\s*"
                     r"(?:Dec[a-z.]*|DEC|δ)?\s*(?:\(J2000(?:\.0)?\))?\s*[=:]?\s*"
                     + SIGN + r"\s*(\d{1,2}\.\d{2,})")
JNAME = re.compile(r"J(\d{4,6}(?:\.\d+)?)" + SIGN + r"(\d{2,6}(?:\.\d+)?)")
GNAME = re.compile(r"\bG(\d{1,3}\.\d+)([+\-−])(\d{1,2}\.\d+)")


def _sign(s: str) -> int:
    return 1 if s == "+" else -1


def _jname(ra: str, sign: str, dec: str) -> tuple[float, float, float] | None:
    """A J-name's place and how coarse it is (degrees)."""
    w = ra.split(".")[0]
    if len(w) == 4:
        h, m, sec, tol = int(w[:2]), float(w[2:] + ("." + ra.split(".")[1] if "." in ra else "")), 0.0, 0.3
    elif len(w) == 6:
        h, m, sec, tol = int(w[:2]), int(w[2:4]), float(ra[4:]), 0.01
    else:
        return None
    d = dec.split(".")[0]
    if len(d) == 2:
        deg, tol = float(dec), max(tol, 1.0 if "." not in dec else 0.1)
    elif len(d) == 3:
        deg, tol = int(d[:2]) + int(d[2]) / 10, max(tol, 0.1)
    elif len(d) == 4:
        deg, tol = int(d[:2]) + float(d[2:]) / 60, max(tol, 0.03)
    elif len(d) == 6:
        deg = int(d[:2]) + int(d[2:4]) / 60 + float(dec[4:]) / 3600
    else:
        return None
    if h > 23 or m >= 60 or deg > 90:
        return None
    return 15 * (h + m / 60 + sec / 3600), _sign(sign) * deg, tol


def positions(text: str) -> list[dict]:
    found = []
    for m in SEXA.finditer(text):
        h, mi, se, _, sg, d, dm, ds = m.groups()
        if int(h) > 23 or int(d) > 90:
            continue
        found.append({"ra": 15 * (int(h) + int(mi) / 60 + float(se) / 3600),
                      "dec": _sign(sg) * (int(d) + int(dm) / 60 + float(ds) / 3600),
                      "as": " ".join(m.group(0).split()), "tol": 0.0})
    for m in DECIMAL.finditer(text):
        ra, sg, dec = float(m[1]), m[2], float(m[3])
        if ra < 360 and dec <= 90:
            found.append({"ra": ra, "dec": _sign(sg) * dec, "as": " ".join(m.group(0).split()), "tol": 0.0})
    for m in JNAME.finditer(text):
        p = _jname(m[1], m[2], m[3])
        if p:
            found.append({"ra": p[0], "dec": p[1], "as": m.group(0), "tol": p[2]})
    for m in GNAME.finditer(text):
        from astropy import units as u
        from astropy.coordinates import SkyCoord
        c = SkyCoord(l=float(m[1]) * u.deg, b=_sign(m[2]) * float(m[3]) * u.deg, frame="galactic").icrs
        found.append({"ra": float(c.ra.deg), "dec": float(c.dec.deg), "as": m.group(0), "tol": 0.01})
    return found


def sep(a: tuple[float, float], b: tuple[float, float]) -> float:
    r1, d1, r2, d2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    x = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2)
    return math.degrees(math.acos(max(-1.0, min(1.0, x))))


MENTIONS = {
    "SPHEREx": re.compile(r"SPHEREx", re.I),
    "A": re.compile(r"Sagittari|\bSgr\b|J1803|18\s?03\s?1[0-5]"),
    "B": re.compile(r"Scorpi|\bSco\b|\bAra\b|\bArae\b|J1652|16\s?52\s?4[0-6]"),
    "C": re.compile(r"\bNorma|\bNor\b|J1606|16\s?06\s?(4[6-9]|5[0-3])"),
}


def report(cache: Path) -> None:
    index = {r["n"]: r for r in json.loads((cache / "index.json").read_text())}
    rows = []
    for file in sorted((cache / "pages").glob("*.txt")):
        n, text = int(file.stem), file.read_text()
        pos = positions(text)
        nearest = {}
        for k, c in CANDIDATES.items():
            d = sorted((sep(c, (p["ra"], p["dec"])), p["as"]) for p in pos)
            if d:
                nearest[k] = {"deg": round(d[0][0], 3), "as": d[0][1]}
        rows.append({"n": n, "date": index[n]["date"], "title": index[n]["title"], "n_positions": len(pos),
                     "positions": sorted({p["as"] for p in pos})[:12], "nearest": nearest,
                     "mentions": [k for k, rx in MENTIONS.items() if rx.search(text)]})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "telegrams_read.json").write_text(json.dumps({"made": now(), "telegrams": rows}, indent=1) + "\n")
    for r in rows:
        near = "  ".join(f"{k} {v['deg']:.2f} deg" for k, v in r["nearest"].items()) or "no position found in the text"
        print(f"{r['n']} {r['date']} {r['title'][:70]!r}: {near}  mentions {r['mentions']}")


if __name__ == "__main__":
    mode, cache = sys.argv[1], Path(sys.argv[2])
    cache.mkdir(parents=True, exist_ok=True)
    if mode == "read":
        read(cache, [int(n) for n in sys.argv[3:]])
    else:
        {"form": form, "report": report}[mode](cache)
