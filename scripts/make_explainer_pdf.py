"""Make documentation/SPHEREx-viewer-explained.pdf: "where does the data come from and what
exactly does the app do", for teammates who are not astronomers.

Every number in the text comes from CLAUDE.md "Verified facts", docs/results.md,
docs/verification.md or docs/search.md; if one of those changes, change it here too.

reportlab is not in the project's own environment (backend/requirements.txt) and should not be
added to it. Run this in a throwaway one instead (nothing is installed into the project):

    uv run -q --python 3.13 --with reportlab python scripts/make_explainer_pdf.py

Optional arguments: the picture of Barnard's Star frames and the output file. Defaults:
documentation/barnard_D5_sheet.png (made by scripts/check_barnard.py) and
documentation/SPHEREx-viewer-explained.pdf. The NEOWISE chart comes from docs/search/.
"""
import math
import sys
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
sheet_png = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "documentation" / "barnard_D5_sheet.png")
out_pdf = sys.argv[2] if len(sys.argv) > 2 else str(ROOT / "documentation" / "SPHEREx-viewer-explained.pdf")
neowise_png = str(ROOT / "docs" / "search" / "serpsouth_neowise_spherex.png")

INK = colors.HexColor("#1b2230")
MUTED = colors.HexColor("#5b6577")
ACCENT = colors.HexColor("#1f5fae")
RULE = colors.HexColor("#d5dae3")
TINT = colors.HexColor("#f2f5fa")
GOOD = colors.HexColor("#1d7a46")
WARN = colors.HexColor("#a35b00")
SIMFILL = colors.HexColor("#fff3dc")

W, H = letter
MARGIN = 0.9 * inch
CONTENT_W = W - 2 * MARGIN

body = ParagraphStyle("body", fontName="Helvetica", fontSize=10.2, leading=14.6, textColor=INK,
                      alignment=TA_LEFT, spaceAfter=7)
small = ParagraphStyle("small", parent=body, fontSize=8.8, leading=12, textColor=MUTED, spaceAfter=4)
cell = ParagraphStyle("cell", parent=body, fontSize=9.2, leading=12.4, spaceAfter=0)
cellb = ParagraphStyle("cellb", parent=cell, fontName="Helvetica-Bold")
head = ParagraphStyle("head", parent=cell, fontName="Helvetica-Bold", textColor=colors.white)
h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=INK,
                    spaceBefore=16, spaceAfter=7, keepWithNext=1)
title = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=23, leading=27, textColor=INK, spaceAfter=4)
subtitle = ParagraphStyle("subtitle", fontName="Helvetica", fontSize=11.5, leading=15, textColor=MUTED,
                          spaceAfter=14)
step_n = ParagraphStyle("step_n", fontName="Helvetica-Bold", fontSize=13, leading=15, textColor=ACCENT)
lead = ParagraphStyle("lead", parent=body, fontSize=11.2, leading=16, spaceAfter=10)
bullet = ParagraphStyle("bullet", parent=body, leftIndent=14, bulletIndent=2)


def P(text, style=body):
    return Paragraph(text, style)


def bullets(items):
    return [Paragraph(t, bullet, bulletText="•") for t in items]


def table(rows, widths, header=True, zebra=True, fill=None):
    data = []
    for r, row in enumerate(rows):
        st = head if (header and r == 0) else cell
        data.append([c if not isinstance(c, str) else Paragraph(c, st) for c in row])
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
             ("TOPPADDING", (0, 0), (-1, -1), 5.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5.5),
             ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), INK)]
    if fill is not None:
        style += [("BACKGROUND", (0, 1 if header else 0), (-1, -1), fill)]
    elif zebra:
        for r in range(1 if header else 0, len(rows)):
            if (r % 2) == 0:
                style.append(("BACKGROUND", (0, r), (-1, r), TINT))
    t.setStyle(TableStyle(style))
    return t


def flow_diagram():
    """Browser <-> our server <-> the public services, with the disk cache underneath."""
    d = Drawing(CONTENT_W, 250)

    def box(x, y, w, h, label, sub, fill, stroke=INK):
        d.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=fill, strokeColor=stroke, strokeWidth=1))
        d.add(String(x + w / 2, y + h - 16, label, fontName="Helvetica-Bold", fontSize=9.6,
                     fillColor=INK, textAnchor="middle"))
        for i, line in enumerate(sub):
            d.add(String(x + w / 2, y + h - 29 - 10.5 * i, line, fontName="Helvetica", fontSize=7.8,
                         fillColor=MUTED, textAnchor="middle"))

    def arrow(x1, y1, x2, y2, label=None, dx=0, dy=5, dashed=False):
        ln = Line(x1, y1, x2, y2, strokeColor=ACCENT, strokeWidth=1.3)
        if dashed:
            ln.strokeDashArray = [4, 3]
        d.add(ln)
        a = math.atan2(y2 - y1, x2 - x1)
        s = 6
        d.add(Polygon([x2, y2, x2 - s * math.cos(a - 0.4), y2 - s * math.sin(a - 0.4),
                       x2 - s * math.cos(a + 0.4), y2 - s * math.sin(a + 0.4)],
                      fillColor=ACCENT, strokeColor=ACCENT))
        if label:
            d.add(String((x1 + x2) / 2 + dx, (y1 + y2) / 2 + dy, label,
                         fontName="Helvetica-Bold", fontSize=10, fillColor=ACCENT, textAnchor="middle"))

    bw, bh = 118, 58
    x_a, x_b, x_c = 0, (CONTENT_W - 150) / 2, CONTENT_W - 150
    mid = 140
    box(x_a, mid, bw, bh, "Visitor's browser", ["the page: search, player,", "charts, practice"], colors.white)
    box(x_b, mid, 130, bh, "Our server", ["Python, FastAPI", "fetches, stacks, measures"], TINT)
    box(x_c, 190, 150, 52, "NASA public S3 copy", ["the SPHEREx images", "(read first)"], colors.white)
    box(x_c, 126, 150, 52, "IRSA archive", ["which images cover a spot;", "fallback for the images"], colors.white)
    box(x_c, 62, 150, 52, "Gaia, SIMBAD, NEOWISE", ["star motions, names,", "other telescope's data"], colors.white)
    box(x_b, 8, 130, 52, "Disk cache", ["patches, frames and", "search answers, kept"], colors.white)

    arrow(x_a + bw, mid + 40, x_b, mid + 40, "1", dy=4)
    arrow(x_b, mid + 14, x_a + bw, mid + 14, "4", dy=-12)
    arrow(x_b + 130, mid + 48, x_c, 216, "2", dx=-6, dy=4)
    arrow(x_b + 130, mid + 30, x_c, 152, "2", dy=4, dashed=True)
    arrow(x_b + 130, mid + 10, x_c, 92, "3", dy=-12)
    arrow(x_b + 45, mid, x_b + 45, 60)
    arrow(x_b + 85, 60, x_b + 85, mid)
    d.add(String(x_b + 93, 98, "save / reuse", fontName="Helvetica", fontSize=7.6, fillColor=ACCENT))
    return d


def status_chip(text, colour):
    return Paragraph(f'<font color="{colour.hexval()}"><b>{text}</b></font>', cell)


story = []
story += [P("How the SPHEREx sky-change viewer works", title),
          P("Where the data comes from, what the app does, and how it checks itself. "
            "Status as of the evening of Saturday 14 November 2026.", subtitle)]

story += [P("<b>In short.</b> The app shows how a small patch of sky changes over time. A visitor gives "
            "a star name or coordinates; our server reads the matching images from NASA's public archive of "
            "the SPHEREx space telescope, cleans and combines them into one picture per <b>visit</b> of the "
            "telescope (one pass over that patch), and plays those pictures in order. Anything that moved or "
            "changed brightness between visits stands out. A <b>blind search</b> can also look through a patch "
            "for movers and changers without being told what to find, and a <b>practice mode</b> lets a "
            "visitor learn to spot a mover on a made-up one. We store no data of our own: everything is "
            "fetched from public archives on request and kept in a cache.", lead),
          P("Words used here. <b>Visit</b>: one of SPHEREx's passes over a patch of sky, made of many "
            "exposures. <b>Detector</b>: one of the telescope's six infrared cameras, D1 (0.75 to 1.12 "
            "microns) to D6 (4.41 to 5.01 microns). <b>Frame</b>: all of one detector's exposures from one "
            "visit, averaged into one picture.", small)]

# ------------------------------------------------------------------ data sources
story += [P("1. Where the data comes from", h1),
          P("Public sources only. None needs an account, a key or payment.")]
src = [["Source", "What we take from it", "How we reach it"],
       ["<b>SPHEREx</b><br/>NASA space telescope, launched March 2025, run by JPL and Caltech",
        "The sky images themselves. SPHEREx photographs the whole sky in infrared light "
        "(0.75 to 5 microns) with six detectors, and comes back to each spot about every six months.",
        "Not directly. Its images are published through IRSA and copied to NASA's public Amazon S3 bucket "
        "(next two rows)."],
       ["<b>NASA's public S3 bucket</b><br/>nasa-irsa-spherex",
        "The same image files as IRSA's. <b>This is where our patches are read from first.</b> A full file "
        "is about 65 MB; we read only the rows of pixels covering the patch we need.",
        "Plain HTTPS requests asking for a byte range of a file. No account."],
       ["<b>IRSA</b><br/>NASA/IPAC Infrared Science Archive at Caltech",
        "A <b>search</b> that answers \"which images cover this point of sky?\", and a <b>cutout</b> service "
        "that sends a small patch of an image. We use the search every time; the cutout service is the "
        "<b>fallback</b> when S3 fails for a patch. IRSA also holds the NEOWISE measurements used for "
        "our outside check (section 8).",
        "Plain web requests to irsa.ipac.caltech.edu. Collections: <font face='Courier'>spherex_dr1</font> "
        "and <font face='Courier'>spherex_qr3</font>."],
       ["<b>Gaia DR3</b><br/>European Space Agency star catalogue",
        "Precise positions of stars and how fast each one moves across the sky. We predict where a star "
        "should be on a given date and compare that with what we measure.",
        "A database query to gea.esac.esa.int."],
       ["<b>SIMBAD</b><br/>name database, Strasbourg",
        "Turns a name (\"Barnard's Star\") into a position and a motion, and tells us an object's type.",
        "A database query over the web."]]
story += [table(src, [1.5 * inch, 3.0 * inch, 2.2 * inch]), Spacer(1, 8)]
story += [P("<b>The direct S3 route.</b> Checked on 14 November: the file our server writes from S3 is byte "
            "for byte the same as the one IRSA's cutout service makes (144 sampled exposures, and all 364 "
            "for Barnard's Star, with 0 differing pixels, header lines or bytes). It is also faster: all six "
            "detectors for Barnard's Star (364 patches) took 42 seconds from S3 against 247 seconds through "
            "IRSA, and a view that is not yet in the cache now answers in about 15 seconds (it was 52)."),
          P("<b>What that looks like for one target.</b> For Barnard's Star the archive holds 364 exposures "
            "from August 2025 to September 2026, about 60 per detector. A patch at our default size is about "
            "a quarter of a megabyte (1,973 patches, 511 MB, for all five test targets). For the blind "
            "search and for checking one candidate we also used two outside records that are not SPHEREx: "
            "NASA's NEOWISE mission (through IRSA) and the AAVSO's observers' brightness records of "
            "variable stars.")]

# ------------------------------------------------------------------ what it does
story += [P("2. What the app does, from the visitor's side", h1)]
does = [["What", "What the visitor sees", "State"],
        ["Search", "A box for a star name or sky coordinates, and buttons for the five challenge targets "
                   "and for our own candidate (section 8). A name is looked up and moved to where the "
                   "object is now.", status_chip("Built", GOOD)],
        ["Player", "The patch as a short video, one frame per visit. Play, pause, step, blink first and "
                   "last, zoom, drag, choose the detector and the size of the patch.",
         status_chip("Built", GOOD)],
        ["Three views", "<b>Normal</b>; <b>Difference</b> (a later visit minus the first: grey is no "
                        "change, white brighter, black fainter); <b>Sum</b> (all exposures added, "
                        "optionally following a moving object).", status_chip("Built", GOOD)],
        ["Markers and Gaia overlay", "Where the object was measured in each frame, its path, and where "
                                     "Gaia says it should be. A line of text gives the measured shift "
                                     "next to Gaia's.", status_chip("Built", GOOD)],
        ["Spectrum", "Click a spot, or press \"Spectrum of the target\": brightness against wavelength, "
                     "one dot per exposure, with a CSV download.", status_chip("Built", GOOD)],
        ["Brightness chart", "\"Brightness over time\": only measurements at the same wavelength are "
                             "compared, and the panel says in words whether the object got brighter, "
                             "fainter, or whether there is too little to say.", status_chip("Built", GOOD)],
        ["Honest labels", "How strong a detection is, a warning when a star is so bright its centre is "
                          "overexposed, when a neighbour is blended in, and when a very bright star nearby "
                          "can leave ghost rings. A Flags switch shows pixels with no data and pixels too "
                          "bright to measure.", status_chip("Built", GOOD)],
        ["Sky context", "The same patch in other surveys (WISE, 2MASS, optical) from the Aladin sky atlas. "
                        "It needs outside servers, which were down for part of 14 November; the panel then "
                        "says so.", status_chip("Built; depends on outside servers", WARN)],
        ["Blind search", "\"Search this patch for anything that moved or changed\": lists what moved or "
                         "changed, how strong, and whether the catalogues already know it (section 7).",
         status_chip("Built", GOOD)],
        ["Practice mode", "\"Practise: find a planted object\": real frames with one made-up object. "
                          "A simulation, labelled as one (section 9).", status_chip("Built", GOOD)]]
story += [table(does, [1.35 * inch, 3.9 * inch, 1.45 * inch])]

story += [P("3. How the pieces connect", h1), flow_diagram(), Spacer(1, 4),
          P("<b>1</b> the visitor's request goes to our server. <b>2</b> the server asks IRSA which exposures "
            "cover the spot, then reads the patches from NASA's S3 copy (the dashed line is the fallback: "
            "IRSA's own cutout service). <b>3</b> it looks up star motions and names, and, for the search, the "
            "catalogues. <b>4</b> it sends back the frames and measurements. Everything downloaded or built "
            "is saved to disk and reused.", small)]

# ------------------------------------------------------------------ how
story += [P("4. How the server builds the frames, step by step", h1),
          P("Each step exists for a reason, given on the right.")]
steps = [
    ("Work out where the object is today",
     "Catalogue positions are for the year 2000. Barnard's Star has drifted 4.5 arcminutes since then, "
     "most of our field of view, so the position is moved forward using the star's known motion. The name "
     "search does this, with a motion from Gaia (or from SIMBAD for an object Gaia does not list)."),
    ("Ask IRSA which images cover that spot",
     "One search request per data collection. The answer lists every exposure with its date, detector "
     "and address."),
    ("Read a small patch of each image",
     "First straight from NASA's S3 copy, six at a time, to be polite to the archive. If a patch fails "
     "there, the same patch is asked of IRSA's cutout service, which fails about one request in three and "
     "so is retried. Each patch is saved to disk and never fetched twice."),
    ("Clean each patch",
     "Subtract NASA's model of the glow from dust in our solar system, remove the leftover sky "
     "brightness, and blank out pixels the archive marks as defective or hit by cosmic rays."),
    ("Line every patch up on one grid",
     "The telescope points at a different angle each time. Each patch is redrawn on the same north-up "
     "grid at 2 arcseconds per pixel (the camera's own pixels are 6.15), so stars land on the same spot."),
    ("Group by visit and average",
     "The key step. A SPHEREx image is not one colour: the colour it records changes across the "
     "detector, so two single exposures of the same star differ in colour, not in time. Averaging the "
     "exposures one detector takes during one visit cancels that out, and also reduces noise. "
     "Stray bad readings are dropped first."),
    ("Use one brightness scale for all frames",
     "If each frame were brightened separately, a star could seem to change when it had not, or a real "
     "change could be hidden."),
    ("Measure the object's position in each frame",
     "A bell-shaped curve is fitted to the object to find its centre to a fraction of a pixel. The "
     "server also computes where Gaia (or the motion given) says it should be on that date. The page "
     "draws a marker only when the thing found really is the object."),
    ("Say how strong the detection is",
     "The same measurement is made at hundreds of empty places in the same frame. The object's value, "
     "divided by how much those empty places scatter, is the strength: \"times the background "
     "scatter\". Weak ones are labelled \"marginal\" (section 6)."),
    ("Send the result",
     "Each frame becomes a PNG picture, plus numbers: dates, how many exposures went in, the colour "
     "range, the measured and predicted positions, the strength and any warnings."),
]
rows = []
for i, (what, why) in enumerate(steps, 1):
    rows.append([Paragraph(str(i), step_n), Paragraph(what, cellb), Paragraph(why, cell)])
t = Table(rows, colWidths=[0.4 * inch, 2.0 * inch, 4.3 * inch])
t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
                       ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                       ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]))
story += [t, Spacer(1, 6),
          P("A repeat request is answered from the cache in a few thousandths of a second.")]

# ------------------------------------------------------------------ proof
img_w = CONTENT_W * 0.8
img_h = img_w * 1119.0 / 1687.0
proof = [["Between visits", "Measured shift (east, north)", "Gaia prediction", "Disagreement"],
         ["1 and 2 (0.56 years)", "-0.93, +5.90 arcsec", "+0.59, +5.63 arcsec", "1.54 arcsec = 0.25 pixel"],
         ["1 and 3 (0.99 years)", "-2.21, +10.16 arcsec", "-0.77, +10.25 arcsec", "1.44 arcsec = 0.23 pixel"],
         ["2 and 3 (0.43 years)", "-1.29, +4.26 arcsec", "-1.37, +4.62 arcsec", "0.37 arcsec = 0.06 pixel"]]
story += [P("5. Proof on real data: Barnard's Star", h1),
          P("Barnard's Star is the fastest-moving star in the sky, about 10.4 arcseconds per year, and is "
            "one of the five test targets the challenge names. These are the three frames the server "
            "produces for it from detector 5 (3.8 to 4.4 microns)."),
          KeepTogether([Image(sheet_png, width=img_w, height=img_h), Spacer(1, 4),
          P("Top row: the full frames, 0.1 degrees across, from August 2025, March 2026 and August 2026. "
            "Green rings mark ordinary stars, which stay put. Bottom row: the centre, enlarged. The red "
            "cross is where the star was in the first frame, the blue ring is where it was measured in "
            "that frame, and the yellow dot is where Gaia predicts it.", small)]),
          Spacer(1, 4), table(proof, [1.45 * inch, 1.8 * inch, 1.65 * inch, 1.8 * inch]), Spacer(1, 6),
          P("The star moves about 10 arcseconds north in a year, as it should, and the measurement agrees "
            "with Gaia to within a quarter of a camera pixel. Ordinary stars in the same frames move by a "
            "median of 0.15 to 0.38 arcseconds (across the six detectors), which shows the frames are "
            "lined up correctly. One honest caution: this star is so bright that its centre is "
            "overexposed (saturated), so its position can only be fixed to about 1 arcsecond in detector 5 "
            "(2 in detectors 1 to 4). The first frame's 1.45 arcsecond offset east is inside that. An "
            "independent check found the fit's own stated error was 10 to 40 times too small for this "
            "star, so the page shows the larger one.")]

# ------------------------------------------------------------------ honest detections
found = [["Target", "What we say", "What to be careful about"],
         ["<b>Barnard's Star</b>", "Moves north about 10 arcsec in a year; the measured shift agrees with "
                                   "Gaia's to 0.23 of a pixel.",
          "Overexposed centre: position good to about 1 arcsec."],
         ["<b>Epsilon Indi B</b><br/>(pair of brown dwarfs)",
          "Visible in all six detectors, moving 6.3 arcsec south-east between April 2025 and October 2026, "
          "on the catalogue's track.",
          "Reflections of a bright star nearby leave ring artefacts in some frames."],
         ["<b>WISE 0855</b><br/>(very cold brown dwarf)",
          "Seen only in detectors 5 and 6. Detector 6: 3.4, 14.6 and 11.2 times the background scatter in "
          "the three visits: <b>marginal, then clear</b>. Moves 8.4 +- 0.4 arcsec west in a year "
          "(catalogue: 8.0).",
          "Visit 1 has three exposures. By visit 3 a neighbouring star 4 arcsec away supplies about a "
          "quarter of the light."],
         ["<b>RW Aurigae</b><br/>(young variable star)",
          "About 1.7 times brighter at the shortest wavelengths and about half as bright at 3.9 to 5 "
          "microns between September 2025 and September 2026. Ground observers saw the same "
          "brightening.",
          "The 2025 exposures fell in a dip of a few days. The fading at 3.9 to 5 microns has no outside "
          "check. A close pair, measured as one."],
         ["<b>R Draconis</b><br/>(bright long-period variable)",
          "Overloads the detectors in every exposure, so no brightness. The star's <b>relative "
          "brightness from its outer light</b> rises and falls by a factor of about 2 to 3, in step with "
          "the 246-day cycle observers record.",
          "A relative measure, not a brightness in physical units, only in detectors 5 and 6."]]
story += [P("6. Honest detections: what we found on the five targets", h1),
          P("The rule: every claim is measured against the same measurement at empty places in the same "
            "picture, and where possible against an outside source. One measurement the fit itself gives, "
            "a \"signal to noise\", is <b>not</b> used as a detection strength: on empty sky it reaches 5 "
            "at about a quarter of places. Each result was also re-measured by a separate session with "
            "separate code (docs/verification.md), and it corrected some earlier claims: RW Aurigae's "
            "\"2.5 times brighter\" compared a dip with a normal state; WISE 0855's older figures included "
            "its neighbour's light."),
          table(found, [1.4 * inch, 3.1 * inch, 2.2 * inch])]

# ------------------------------------------------------------------ search
story += [P("7. The blind search", h1),
          P("The challenge is to spot things that move. The blind search is given a patch of sky and nothing "
            "else, and does it for every source in the patch. For each of the six detectors it:"),
          *bullets([
              "builds one frame per visit and one of all visits together, in the same way as the viewer;",
              "finds every source that stands out clearly (5 times the noise), with no catalogue;",
              "measures each source's position in every visit, and asks whether it drifts in a straight "
              "line by more than its own error;",
              "measures each source's brightness in every exposure and compares visits <b>at the same "
              "wavelength</b>;",
              "tries to kill every candidate with tests for the artefacts SPHEREx makes: reflections "
              "(\"ghosts\") of bright stars, overlapping glitches, saturated stars, blended neighbours, "
              "a change resting on one pair of exposures;",
              "looks up what survives in five catalogues (Gaia DR3, SIMBAD, AAVSO's variable star index, "
              "CatWISE2020, AllWISE), with each catalogue position moved to the date of each visit.",
          ]),
          Spacer(1, 4),
          P("Each survivor ends as <b>clean</b>, <b>caution</b> (flags a person must look at) or "
            "<b>rejected</b> (it has an artefact's signature; the reasons are written out). It is also "
            "labelled: already known, or <b>candidate</b> when no catalogue we asked lists it. A search "
            "that finds nothing says so. On the page it is the button \"Search this patch for anything "
            "that moved or changed\"; a patch whose images are on disk takes 20 to 50 seconds, and a new "
            "one about three minutes."),
          P("<b>Result 1: given only the field centres,</b> it found Barnard's Star, WISE 0855 and Epsilon "
            "Indi B moving, and RW Aurigae changing, each labelled as already known. In 30 searches on the "
            "five challenge fields (683 sources tested for motion, 663 for brightness) it reported 5 "
            "objects, all of them the targets, with no false alarm found by eye. One artefact reached a "
            "strength of 7.0 times the noise: the ghost of the bright star Epsilon Indi A. It was rejected, "
            "because it was missing from two of the four visits at the place its \"motion\" predicted and "
            "was not point-like. Five objects in 30 searches is a small sample: the false-mover rate is "
            "below about 1 in 230 sources (95 per cent confidence), not zero."),
          P("<b>Result 2: four young star clusters</b> (NGC 1333, Serpens Main, Serpens South, Chamaeleon "
            "I), where young stars vary and many are hidden from optical surveys. Of 28 objects that passed: "
            "17 are listed variable stars, 2 are candidates that survive every test, and 9 could be "
            "neither confirmed nor ruled out. No mover without a catalogue counterpart survived anywhere. "
            "In busy, nebulous fields a change seen in one detector cannot be told from an artefact, so we "
            "quote only changes seen the same way in two or more detectors.")]

# ------------------------------------------------------------------ candidate
cand = [["", "Faintest", "Brightest", "Range"],
        ["NEOWISE, 4.6 microns, 2014 to 2024", "177 mJy (March 2024)", "1,603 mJy (September 2017; partly "
                                                                          "saturated)", "factor 9"],
        ["SPHEREx, 4.0 to 5.0 microns", "178 mJy (September 2025)", "805 mJy (September 2026)",
         "factor 4.5"]]
story += [P("8. The Serpens South candidate, and the check against NEOWISE", h1),
          P("The strongest candidate of the whole hunt is an embedded young star at RA 277.50547, Dec "
            "-2.06198 (SIMBAD: MSX6C G028.6477+03.8174, a young stellar object). Between September 2025 and "
            "March 2026 it became about five times brighter at 2.4 to 5 microns, and stayed bright through "
            "September 2026. It is not listed as variable in Gaia DR3, AAVSO's variable star index, "
            "SIMBAD's object type or AllWISE's variability flag. It changes the same way in three "
            "detectors at 5 times the noise or more, and survives leaving out the two exposures that "
            "help most."),
          P("<b>The outside check.</b> The search compares SPHEREx with itself. To test the candidate from "
            "outside, we asked NASA's archive for every measurement of this position that the NEOWISE "
            "mission made from 2014 to 2024: 485 single exposures within 8 arcsec, 269 of them within 1.5 "
            "arcsec on frames NEOWISE rates usable, in 21 visits about half a year apart. We also measured "
            "the SPHEREx images again with the viewer's own brightness code, which shares nothing with the "
            "search."),
          KeepTogether([Image(neowise_png, width=CONTENT_W * 0.88, height=CONTENT_W * 0.88 * 828.0 / 1100.0),
                        Spacer(1, 3),
          P("Grey dots: NEOWISE, the median of each visit (hollow: partly saturated, so less certain). "
            "Coloured squares: SPHEREx, each visit. Top: 4.6 microns. Bottom: 3.4 microns. Both telescopes "
            "blur about 6 arcseconds, so both measure the same tight group of stars together.", small),
          table(cand, [2.4 * inch, 1.45 * inch, 1.95 * inch, 0.9 * inch])])]
story += [Spacer(1, 6),
          P("<b>What it settles.</b> The star really does vary, by a factor of 7 to 9, in a different "
            "telescope's data. NEOWISE's last visit, in March 2024, found it at 177 mJy at 4.6 microns, "
            "fainter than in any of its 20 earlier visits; SPHEREx's first visit, in September 2025, found "
            "178. In March, May and September 2026 SPHEREx has it at 793, 656 and 805 mJy, back inside "
            "NEOWISE's usual range. So what SPHEREx watched is the star <b>coming back from a dip</b>, the "
            "deepest of the ten years, not a first outburst and not a new kind of event."),
          P("<b>What stands, and what does not.</b> None of the lists we asked records it as variable, "
            "although its variability is plain in NEOWISE's public data. It is very likely known to "
            "specialists who study young stars; we did not check their tables. SPHEREx adds the rise seen "
            "in 102 colours at once. It is still a <b>candidate</b>, and nobody can say which star of the "
            "tight group is the one that varies."),
          P("What we say: \"not listed as variable in the catalogues we asked\". What we do not say: "
            "\"new\", \"discovered\", \"erupted\".", small)]

# ------------------------------------------------------------------ practice mode
sim = [["Safeguard", "How"],
       ["Its own door", "A separate endpoint, <font face='Courier'>/api/training</font>. The real "
                        "<font face='Courier'>/api/frames</font> never contains it."],
       ["Its own files", "Frames are built in their own <font face='Courier'>training-</font> folders, "
                         "never in the real cache."],
       ["Says so in the data", "Every answer carries <font face='Courier'>simulation: true</font> and a "
                               "notice."],
       ["Says so in the picture", "The word SIMULATION is drawn into every image, bottom right, so a "
                                  "screenshot cannot lose it."],
       ["Says so on the screen", "A banner at the top that cannot be closed, and none of the real view's "
                                 "panels (no measurements, no charts)."],
       ["Cannot reach a measurement", "It never reaches <font face='Courier'>/api/frames</font> or any "
                                       "measurement."]]
story += [P("9. The practice mode, and why it is safe", h1),
          P("The challenge is to spot something that moves. Practice mode lets a visitor try it on real "
            "images, with an object whose answer is known. It is <b>the only simulated thing in the "
            "project</b>: one made-up object is added to the real stacked frames of each visit, and the "
            "visitor clicks where they think it is. A hint and \"Show me\" reveal it."),
          P("The object has a real star's shape (the median of 57 to 135 isolated stars per detector). "
            "It moves the way a body far beyond Neptune would, with a yearly swing and a slow drift; the "
            "distance is set so the swing is 22 to 38 per cent of the picture, about 4,000 to 4,800 times "
            "the Earth-Sun distance at the default size. At the medium level its peak is 7 times the "
            "frame's background scatter, which is hard to see in the ordinary frames and plain in the "
            "difference frames (easy 12, hard 4.5)."),
          table(sim, [1.9 * inch, 4.8 * inch], fill=SIMFILL), Spacer(1, 6),
          P("What it is not: a detection, or a discovery. Nothing from practice mode is used in any "
            "result in this document.")]

# ------------------------------------------------------------------ status + limits
status = [["Part", "State"],
          ["Frames, difference and sum views, name search, player, Gaia overlay, spectrum and brightness "
           "chart, flags", status_chip("Built and looked at on the real page", GOOD)],
          ["Reading patches straight from NASA's S3 bucket, with IRSA as fallback",
           status_chip("Built and checked", GOOD)],
          ["Blind search and its panel on the page; the NEOWISE check", status_chip("Built and checked", GOOD)],
          ["Practice mode", status_chip("Built", GOOD)],
          ["Putting it online (a public address)", status_chip("Not done yet", WARN)],
          ["Recording the demo video; filling in the submission form", status_chip("Not done yet", WARN)]]
limits = [
    "<b>Only three or four visits.</b> SPHEREx revisits a spot about every six months and began in 2025, "
    "so each target has three or four frames and the video is short.",
    "<b>Motions are small.</b> Even the fastest star moves only one to three camera pixels between visits, "
    "and two objects closer than a pixel (6.15 arcsec) blur into one.",
    "<b>Bright stars overload the camera.</b> Barnard's Star is blank at its centre in detectors 1 to 4 and "
    "clean only in 5 and 6; R Draconis is overexposed in every exposure, so it gets a relative measure only.",
    "<b>Fast objects are averaged away.</b> A frame averages weeks of exposures, so asteroids and comets, "
    "which move within a visit, are not found. The search cannot find objects that are too faint, move "
    "slower than about 1.2 to 2 arcsec a year, move faster than about 16, or change by less than about "
    "10 per cent.",
    "<b>The archive is slow.</b> A new position takes about 15 seconds when NASA's S3 copy answers, about a "
    "minute through IRSA. For the demo, the targets are loaded into the cache beforehand.",
    "<b>Outside servers fail.</b> The sky-context panel and name lookup depend on them; both say so when "
    "they fail.",
    "<b>The blind search is tested on few fields.</b> No false alarm in ordinary star fields, but young "
    "clusters give changes that cannot be confirmed, and fields like the crowded Galactic plane were not "
    "tried.",
]
story += [P("10. What is built and what is not", h1),
          table(status, [4.3 * inch, 2.4 * inch]), Spacer(1, 4),
          P("11. Limits worth knowing", h1)]
story += bullets(limits)
story += [Spacer(1, 10),
          P("Data credits: SPHEREx images, NASA/JPL-Caltech. Archive, NASA/IPAC Infrared Science Archive "
            "(IRSA). Star positions and motions, ESA Gaia DR3. Names, SIMBAD (CDS, Strasbourg). Brightness "
            "check, NEOWISE (NASA/IPAC IRSA) and AAVSO observers. Sky atlas, Aladin Lite (CDS). Built by "
            "Team Ampersand for NASA Space Apps 2026.", small)]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.line(MARGIN, 0.65 * inch, W - MARGIN, 0.65 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 0.48 * inch, "SPHEREx sky-change viewer: how it works")
    canvas.drawRightString(W - MARGIN, 0.48 * inch, f"Page {doc.page}")
    canvas.restoreState()


doc = SimpleDocTemplate(out_pdf, pagesize=letter, leftMargin=MARGIN, rightMargin=MARGIN,
                        topMargin=0.85 * inch, bottomMargin=0.9 * inch,
                        title="How the SPHEREx sky-change viewer works", author="Team Ampersand")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("wrote", out_pdf)
