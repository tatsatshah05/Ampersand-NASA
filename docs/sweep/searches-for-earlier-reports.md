# Searches for earlier reports of Candidates A, B and C

Written 2026-11-15. This file is the record of every search made for an earlier report of the sweep's three
candidates (`docs/sweep.md`), and the checklist a person must still work through. It keeps, in the repository,
what was first written in temporary folders:

- the wider search for earlier reports (a second round, made after the referee's ruling): its verdict and every
  search, copied from `docs/sweep/vetting/recheck_reports.json`;
- the telegram check made after that (`docs/sweep/vetting/atel_by_hand/RESULT.md`, with the search form's own log
  in `searches.json` beside it);
- what has not been searched;
- the checklist for a person, with a place to write the date and result of each check.

**Nothing has been reported anywhere.** No form was filled, no account was made, nothing was sent or posted.
Every search below only read public pages. The draft texts in `docs/sweep/report-draft.md` are not sent.

The positions are the corrected ones (J2000), never the sweep's first ones:

| Candidate | RA, Dec (degrees) | RA, Dec (hours and degrees) | Constellation |
|---|---|---|---|
| A | 270.80408, -23.46818 | 18:03:12.98, -23:28:05.4 | Sagittarius |
| B | 253.18038, -44.67697 | 16:52:43.29, -44:40:37.1 | Scorpius |
| C | 241.70906, -52.20564 | 16:06:50.17, -52:12:20.3 | Norma |

Words used: a **control** is a known object that the same search must find. If the control is not found, the
search did not work, and its empty answer means nothing. Only searches with a passing control count as
searched.

## (a) The wider search for earlier reports

Three searchers, one per candidate, worked on 2026-11-15 from about 07:01 to 07:37 UTC. A referee then read
their reports and gave the verdict below. The first round of searches (for A, 04:12 to 05:45 UTC) was part of
the vetting that led to the ruling (`docs/sweep/vetting/reviews_*.json`, the "reports" lens; summed up in
`docs/sweep.md`).

### The verdict

> No earlier report was found for A, B or C. None of the three searchers found a report of a transient within
> 30 arcsec of any candidate, or a named 2025-26 event within 5 arcmin, in either round. All three stay
> 'candidate', and the earlier ruling's public sentences still hold.

The verdict counts only searches with a passing control. Across both rounds that is more than 30 catalogues and
alert lists per candidate. Only some of them hold objects of 2025-26, so only they could carry a report of these
brightenings: the Transient Name Server (TNS); AAVSO VSX, live and in VizieR's copy of 2026-10-18 (which holds
the 2026 novae V419 Mus and V2104 Aql); Koji Mukai's confirmed-nova list (11 Nov 2026) and the CBET titles (to
14 Nov 2026); CBAT's list of unconfirmed transients (TOCP) and the ASAS-SN transients page; vsnet-alert, MAXI
and the Fermi-LAT nova list; the titles of the Astronomer's Telegrams and the BAA circulars; and for A only, the
ZTF alert brokers. The older catalogues (GCVS of 2020, Gaia DR3 with data to 2017, VVV of 2010-19, the nova
catalogues to 2015-22) show only that no known variable star or earlier eruption sat at these places.

Closest things found, from the verdict:

- Within 30 arcsec only C has catalogued neighbours, and none is a transient or a report: a Gaia star of the
  RS type at 11.95 arcsec, a VVV contact binary at 15.46 arcsec and a Herschel cold-dust clump at 3.65 arcsec.
  The two stars were catalogued before 2025, are periodic, and are different stars, because C's position is good
  to 0.3-0.5 arcsec.
- For A and B the nearest catalogued variables are 33.8 and 33.3 arcsec away.
- Nearest named events of 2025-26: for A, AT 2025qzs (a cataclysmic-variable candidate) 37 arcmin away and the
  nova AT 2026abbx 2.56 deg away; for B, X-ray bursts of the known burster 4U 1705-440, 2.4 deg away; for C,
  the HP Nor dwarf-nova outburst 3.39 deg away and the new X-ray nova MAXI J1609-487 3.46 deg away.

The verdict ends: "This verdict therefore records which searches ran, that they worked and what they returned;
it is not proof that no one else has seen these objects. Nothing has been submitted anywhere."

### What may be said, per candidate

These are the referee's sentences (`what_can_be_said`), written before the telegram check in (b):

- **A:** "We checked more than 30 public catalogues and alert lists, each tested on a known object, and found no earlier report of a new or brightening object at Candidate A's position in Sagittarius; some sources, including the full text of The Astronomer's Telegram and NASA's Astrophysics Data System, have not yet been searched, so this does not prove that no one else has seen it."
- **B:** "We checked more than 30 public catalogues and alert lists, each tested on a known object, and found no earlier report of a new or brightening object at Candidate B's position in Scorpius; some sources, including the full text of The Astronomer's Telegram and NASA's Astrophysics Data System, have not yet been searched, so this does not prove that no one else has seen it."
- **C:** "We checked more than 30 public catalogues and alert lists, each tested on a known object, and found no earlier report of a new or brightening object at Candidate C's position in Norma (two ordinary variable stars catalogued before 2025 lie 12 and 15 arcseconds away and are different stars); some sources, including the full text of The Astronomer's Telegram and NASA's Astrophysics Data System, have not yet been searched, so this does not prove that no one else has seen it."

Since then the telegram check (b) searched the telegrams' full text by keyword, through the site's own search
form, and found nothing at the three places; no person has yet read the telegrams in full or made the rest of the
checks in (d). The checklist says when the clause about sources not yet searched may be dropped: only when its
steps 1 to 3 pass their controls and find nothing. That has not happened, so the clause stays.

### The searches that worked, candidate by candidate

Each entry gives the source, the time (UTC, 2026-11-15), the control and what came back, as the searcher
recorded it. "Partly" means the search ran but covers only part of what was asked, or its control was weak; it
is listed separately. Searches that did not work are in (c).

#### Candidate A (Sagittarius)

Earlier report found: **no**.

Second round, each search with a passing control:

- **VizieR's own catalogue search (-meta), CfA and IDIA mirrors** (2026-11-15 07:04:31-07:14:00). Control: The meta service returns the known record for J/MNRAS/465/3011, and keyword searches return known catalogues (for example, SPICY returns J/ApJS/254/33). Result: Identifiers found: J/MNRAS/465/3011 (Contreras Pena+2017a, 816 VVV high-amplitude variables), J/MNRAS/465/3039 (Contreras Pena+2017b), J/MNRAS/472/2990 (Lucas+2017 UGPS eruptive YSOs), J/ApJ/864/11 (Medina+2018 VVV V4), J/MNRAS/509/2566 (VIVACE), J/ApJS/254/33 (SPICY), I/358 (Gaia DR3 variability), II/366 (ASAS-SN variables), B/gcvs (GCVS 5.1 Oct 2020 + NSV), B/vsx (2026-10-18). Novae and CVs: J/ApJ/834/196, J/MNRAS/517/6150, J/ApJ/788/164, J/A+A/554/A123, J/ApJ/912/19, B/cb, V/123A, J/AcA/64/197; also J/ApJ/920/132. NOT in VizieR, 'Table or Catalog not found' on both mirrors: Lucas+2024 (J/MNRAS/528/1789), Guo+2024 (J/MNRAS/528/1769), Contreras Pena+2024 (J/MNRAS/528/1823), VIVA (J/MNRAS/496/1730).
- **VizieR (CfA mirror): VVV and VVVX eruptive and high-amplitude variable catalogues** (2026-11-15 07:15:58-07:16:19 and 07:35:39-07:35:46). Control: PASSED for each: a 60" cone at a member's own position returns it at 0.00". Members used: VVVv1 (175.39650 -62.34875) for 465/3011, VVVv20 for 465/3039, UGPS J032726.66+584508.5 for 472/2990, and the first V4 row (174.13270 -63.58779). Result: 0 rows within 1', 10' and 1 degree in all four.
- **VizieR: VIVACE (J/MNRAS/509/2566/vivace)** (2026-11-15 07:16:20-07:16:32). Control: PASSED: the nearest member, re-queried at its position, is found at 0.001". Result: 5 within 1': EA/EB at 33.8", 38.9" and 43.5", Ell at 52.0", EA/EB at 57.3". 326 within 10' (for example LPV at 63.3"). 16,176 within 1 degree. Nothing within 30".
- **VizieR: SPICY (J/ApJS/254/33/table1)** (2026-11-15 07:16:33-07:16:38). Control: PASSED: SPICY 72045 found at 0.0" by a 60" cone at its SIMBAD position. Result: 0 within 1'. 18 within 10': SPICY 72045 (Class I) at 100.5", 72046 (Class II) at 162.0", 72096 (FS) at 169.1", 71976 at 226.7", 72047 at 235.8". 1,612 within 1 degree.
- **VizieR: Gaia DR3 variability (I/358/vclassre, I/358/varisum, I/358/scalerts)** (2026-11-15 07:16:47-07:17:06 and 07:35:47-07:35:52). Control: PASSED: Gaia DR3 4069172520146611584 found at 0.09". Gaia16akk found at 0.001" in scalerts. Result: vclassre: 1 within 1', Gaia DR3 4069172520146611584 (LPV) at 43.0". 69 within 10'. 5,126 within 1 degree: 3,177 LPV, 882 ECL, 362 YSO, 1 CV at 44.7', 1 microlensing. varisum: 1 within 1' and 70 within 10'. scalerts: 0, 0, 0. The data end in 2017, so this checks only for a variable progenitor.
- **VizieR: ASAS-SN variable stars (II/366/catv2021)** (2026-11-15 07:17:09-07:17:25). Control: PASSED: the nearest member is re-found at 0.0". Result: 0 within 1'. 11 within 10': ROT: at 177.1", EB at 314.4", RRC at 396.5", SR at 517-547". 451 within 1 degree, the only CV-type a UGSU at 53.9'.
- **VizieR: GCVS 5.1 (B/gcvs/gcvs_cat) and New Suspected Variables (B/gcvs/nsv_cat)** (2026-11-15 07:17:26-07:17:37). Control: PASSED: V1950 Sgr found at 0.12". NSV 24077 re-found at 0.0". Result: GCVS: 0 within 1'. 1 within 10': V1950 Sgr (M; OH/IR) at 588.7". 73 within 1 degree: 41 IN-type, V3899 Sgr INSB at 644", V4578 Sgr WR at 786", V5410 Sgr SRA at 880", and no N-type. NSV: 0 within 1' and 10'. 138 within 1 degree, nearest NSV 24077 at 21.6'. This VizieR GCVS version (Oct 2020) carries no designations assigned after 2020.
- **VizieR: VSX copy (B/vsx/vsx, version 2026-10-18)** (2026-11-15 07:17:38-07:17:42). Control: PASSED: V7994 Sgr (NA, 2025 nova) found at 3.7" by a 60" cone at 270.97042 -31.45828. Result: 1 within 1': Gaia DR3 4069172520146611584 (type L) at 43.1". 76 within 10': E, L, RS, VAR, SR|M, YSO, and no N- or CV-type. Run before I read aavso.org's robots.txt (see not_searched).
- **VizieR: nova and CV catalogues (Shafter 2017 J/ApJ/834/196; Schaefer 2022 J/MNRAS/517/6150; Pagnotta+2014 J/ApJ/788/164; Saito+2013 VVV-area novae J/A+A/554/A123; De+2021 PGIR novae J/ApJ/912/19; Ritter&Kolb B/cb; Downes V/123A; OGLE-IV transients J/AcA/64/197)** (2026-11-15 07:17:43-07:18:43). Control: PASSED for each: the nearest member (V4742 Sgr, V5588 Sgr, V6593 Sgr), or the first row (V1017 Sgr in B/cb, BE Oct in V/123A, 12-NOVA-02 in OGLE), is re-found at 0.0". Result: 0 rows within 1 degree in all. Nearest novae within 10 degrees: V5588 Sgr (2011) at 1.68 deg (Schaefer, Saito); V4742 Sgr (2002) at 1.88 deg (1.21 deg with Shafter's coordinates); V4157 Sgr, V1583 Sgr and V1148 Sgr at 2.7-2.9 deg; nearest PGIR nova V6593 Sgr at 2.82 deg. These catalogues end in 2015-2022.
- **vsnet-alert public archive** (2026-11-15 07:16:17 (list); messages 07:17-07:25; Sesame 07:22-07:24; TNS 07:23:00-07:23:06). Control: Partly passed. V462 Lup (ASASSN-25cm, msg 28074, 2025-06-14), V572 Vel (PNV J10251200-5331109, msg 28082) and V4371 Oph (msg 28106) appear. V7994 Sgr, V8055 Sgr and V8056 Sgr were never announced on vsnet-alert, so the list does not carry every nova. Result: 159 messages dated 2025-08-01 to 2026-11-13. Sgr and neighbouring constellations, with distances from A: V4371 Oph = TCP J17301230-2753488 = AT 2025wyg (classical nova, 2025-09-07) 8.65 deg; UZ Ser (DN outburst, 2026-05-21 list) 8.76 deg; MAXI J1750-327 (X-ray nova, 2026-08-17) 9.69 deg; V390 Sco ('SCOV390 brightening', 2026-08-25) 13.00 deg; AS 221 (possible symbiotic nova, 2025-11-10) 14.49 deg; V478 Sco 14.52 deg; BP CrA 15.71 deg; NSV 11274 (Tel) 24.48 deg; TCP J16271026-1030020 (Oph, WZ Sge DN, 2025-08) 26.30 deg; ASASSN-26ew (Sgr, SU UMa DN, 2026-08) 27.93 deg; AT 2026ryu (Aql DN, 2026-07) 28.93 deg; FO Aql 29.57 deg; X Ser (2026-10-08) 32.74 deg; V2276 Sgr 35.59 deg; TCP J18030904+1218140 (Oph, AM CVn, 2026-08/09) 35.77 deg; CM Mic 37.26 deg; AT 2026rdg = V2104 Aql (reddened nova, 2026-07-01) 39.58 deg; TCP J20143906+0352503 (Aql) 42.11 deg; TT Ind 42.88 deg; V1047 Aql 43.43 deg; PQ Aql 45.29 deg; V1885 Aql not resolved (Aquila, at least about 11 deg from A). Nothing within 8.6 deg.
- **MAXI nova alert (flash report) page and MAXI news** (2026-11-15 07:27:25-07:27:29). Control: PASSED: MAXI J1750-327 (2026-08-13) and MAXI J1609-487 (2026-10-28 and 10-31) are listed. Result: 2,002 flash reports from 2010-02-02 to 2026-11-10, 161 since 2025-08-01. Nearest since 2025-08: an X-ray burst from XTE J1810-197/-189 (2026-09-12) at 3.63 deg; V4641 Sgr (2026-01/02) at 4.16 deg; SAX J1748.8-2021 at 4.55 deg; GS 1826-238 bursts at 5.0-6.2 deg. Nothing within 3.6 deg. The news page lists nothing at A.
- **Fermi-LAT detected novae list (K. Mukai, NASA GSFC)** (2026-11-15 07:25:22). Control: PASSED: V7994 Sgr and V462 Lup are listed. Result: LAT novae in 2025-26: V462 Lup, V572 Vel, V7994 Sgr (7.99 deg), V1935 Cen, Fermi J1820-1648 ('Nova in Sagittarius', LAT transient found 2026-02-18; 18 20 24.66 -16 53 36.7) at 7.71 deg, and V8056 Sgr (2026-10) at 4.60 deg. No LAT nova near A.
- **CBAT public list of CBET titles (designations)** (2026-11-15 07:33:46). Control: PASSED: V7994 Sgr (CBET 5612, 5615) is listed. Result: Sgr designations for 2025-26: V7991, V7992, V7993 Sgr (TCP J18022164-3310319, 9.71 deg) and V7994 Sgr in 2025; V8055 Sgr = Nova Sgr 2026 No. 3 = TCP J18251276-2225293 (CBET 5724, 5.17 deg) and V8056 Sgr = TCP J17541876-2736362 (CBET 5763, 4.60 deg) in 2026. Neighbours: V4371 Oph (8.65 deg), V691 Ser, V2104 Aql. None near A.
- **Open-web name searches (WebSearch tool)** (2026-11-15 about 07:25-07:33 (WebSearch calls are not time-stamped; times are bracketed by the logged requests)). Control: PASSED: the 'Nova Sagittarii 2025' search returns V7994 Sgr = N Sgr 2025 No. 4 = TCP J18035290-3127298. Result: No page mentions A's position, J-name or Galactic name. Found: V7991-V7994 Sgr (2025); V8055 Sgr (Nova Sgr 2026 No. 3, 2026-08-19, about 8.4 V); Fermi J1820-1648 (gamma-ray transient 2026-02-18, ATel 17688/17689/17698/17700; not opened). PNV J18365700-2855420 is V5668 Sgr from 2015. Nova Sgr 2026 Nos. 1 and 2 were not identified in open sources. They may be Fermi J1820-1648 and PRIME26aaabsh, both 'Nova in Sagittarius' in early 2026 and 6.8-7.7 deg from A; this is unverified.
- **Koji Mukai's confirmed and unconfirmed nova lists (local copies saved by the first review; page dates 11-Nov-2026 and 12-Jan-2026), re-parsed for every 2025-26 entry** (2026-11-15 07:29 (parse)). Control: PASSED: V7994 Sgr, V462 Lup and V691 Ser are present. Result: 23 confirmed entries for 2025-26. The nearest is TCP J17520680-2343207 = ASASSN-26fc = AT 2026abbx ('Nova in Sagittarius', 2026-09-08, 11.3 mag) at 2.56 deg. Next: V8056 Sgr 4.60, PRIME26ahygn (Oph, 2026-03-28, H=11.1) 5.17, V8055 Sgr 5.17, V7991 Sgr 6.59, PRIME26aaabsh (2026-03-10, H=11.4, 'first detection after a seasonal data gap') 6.76, PRIME25aaghjd 7.21, Fermi J1820-1648 7.71, V7994 Sgr 7.99 and V4371 Oph 8.65 deg. Unconfirmed list: only AT 2025sqe (36 deg) is from 2025-26.

Second round, partly:

- **SIMBAD mirror at IDIA (official CDS alternative), TAP** (2026-11-15 07:06:39-07:06:47 (name controls 07:07:19-07:08:19)). Control: FAILED. The same 2-arcmin cone at V462 Lup (227.01362, -40.14308) returns only 4 field stars. Name lookups return nothing for V462 Lup, V7994 Sgr, V572 Vel, V8056 Sgr and V615 Vul; V1723 Sco (Feb 2024) and V1716 Sco are found. The mirror has no 'NOVA ... 2025/2026' identifiers and no 'AT 2026' identifiers, and its newest ATel reference is 2025ATel17100. It cannot speak to 2025-26 events. Result: 2 arcmin: 3 objects, none a transient: 2MASS J18031598-2327530 (LP?) at 43.1", Gaia DR3 4069173447841928576 (EB*) at 89.7", SPICY 72045 (Y*?) at 100.5". 30 arcmin: 2,017 objects with no No* or No? type. Transient-like types: X-ray 1RXS J180348.7-233006 at 8.4', V3899 Sgr (Or*) at 10.7', CV* 2XMM J180235.9-231332 at 16.9', and the gamma-ray sources 1FIG J1801.4-2330 and 0FGL J1801.6-2327 at about 20.5'.
- **SIMBAD mirror at CfA, TAP** (2026-11-15 07:34:05-07:34:09 (name controls 07:08:47-07:10:28)). Control: FAILED. V462 Lup and V7994 Sgr are absent by name and by cone; V1723 Sco is found. Result: 2 arcmin: 4 objects, the IDIA three plus Gaia DR3 4069172863743999360 (*) at 102.6". 30 arcmin: 2,081 objects. The 79 objects not on IDIA are stars, YSOs and Em* stars, and none is a nova or transient.
- **arXiv HTML of the 2024 VVV eruptive-variable papers (not in VizieR)** (2026-11-15 07:30:06 (abs page), 07:30:24, 07:30:41, 07:30:58). Control: Positions parse consistently: 'VVV J163637.94-474444.1 249.15809 -47.74558' is recovered identically from the name and from the columns. Result: Lucas+2024: the HTML has only example rows (27 J-names, nearest 29.8 deg); the full 222-source list is in ancillary files, not read. Guo+2024: 20 L222 positions; nearest L222_192 (269.43525 -24.34244, eruptive) at 1.53 deg. Contreras Pena+2024: no positions in the HTML (tables are supplementary). The first review found the VIRAC2 source 1.5" from A steady over 119 epochs, so A cannot be a ΔKs>4 member of Lucas+2024 in any case.
- **Wikipedia** (2026-11-15 07:26:10-07:26:14). Control: PASSED: V462 Lup is listed. Result: 2025 entries: V462 Lup (+5.7), V572 Vel (+4.8), V1935 Cen (+5.8). No 2026 entry. The list covers bright novae only. The '2025' and '2026' pages do not exist (HTTP 404).
- **British Astronomical Association** (2026-11-15 07:28:31; 07:32:47-07:32:57). Control: PASSED: V2104 Aql (N Aql 2026) is found in VSSC209. Result: Forum thread: HTTP 404 'Page not found' to an anonymous reader, probably members-only; not pursued. VSS Circular 208 (June 2026) mentions AT2026lck. VSS Circular 209 (September 2026) covers V2104 Aql, V1452 Tau and V488 Sge. Neither mentions anything near 18h03m -23d28m, Sgr novae or SPHEREx. VSSC210: 404, not yet published.

First round (earlier ruling, 04:12-05:45 UTC), with controls:

- TNS at 60 arcsec and 1 deg: no results. The nearest 2025-26 entry is AT 2025qzs, a CV candidate 37 arcmin away.
- AAVSO VSX live: only an unrelated type-L star 43.9 arcsec away.
- ASAS-SN transients, CBAT TOCP and Mukai's lists: nothing within 1 deg.
- ZTF brokers ALeRCE, ANTARES and Fink: the nearest object is 35.9 arcsec away and unrelated.
- ATel titles of 942 telegrams plus 22 keyword searches: the nearest Sgr nova or infrared transient is at least 4.6 deg away.
- Karambelkar et al. 2026 and Li, Wang & Lin 2026: A is not in them.

#### Candidate B (Scorpius)

Earlier report found: **no**.

Second round, each search with a passing control:

- **VizieR catalogue search (CfA mirror, vizier.cfa.harvard.edu)** (2026-11-15 07:04:24-07:11:24). Control: The mirror is current: it holds catalogues published in 2026 (e.g. J/A+A/714/A98, J/A+A/712/A191). Result: Identifiers found: J/MNRAS/472/2990 (Lucas+2017 eruptive YSOs); J/MNRAS/465/3011 and J/MNRAS/465/3039 (Contreras Pena+2017); J/MNRAS/486/4590 (Contreras+2019); J/MNRAS/495/3614; J/ApJ/864/11 (VVV V4); J/MNRAS/509/2566 (VIVACE); J/A+A/660/A35 (VVV LPVs); J/A+A/693/A28 (VVV/WISE Miras); J/ApJS/254/33 (SPICY); J/ApJS/278/10 (SPICY WISE variability, Neha+2025); J/ApJS/272/44 (ATLASGAL NEOWISE variability); J/ApJ/883/6; J/ApJ/920/132; J/ApJ/839/88 (SPRITEs); J/A+A/619/A41; J/A+A/703/A141 (VVV-WIT-13 photometry only); I/358 (Gaia DR3 variability); II/366/catv2021 (ASAS-SN variables); B/gcvs (GCVS, NSV); novae J/A+A/554/A123, J/ApJ/834/196, J/MNRAS/517/6150, J/ApJ/788/164, B/cb, V/123A. Not on VizieR (0 resources): Lucas+2024 (MNRAS 528, 1789), Guo+2024 (528, 1769), Guo+2021 (504, 830). No VVVX variability catalogue exists apart from tile coordinates and a Carina YSO list.
- **VizieR cone searches, 31 tables (CfA mirror)** (2026-11-15 07:08:07-07:11:11). Control: For every table, the first row was re-found at 0.0 arcsec by the same 10-arcsec cone. Cone controls: the GCVS and Schaefer 2022 cones returned V1662 Sco at 44.6 arcmin; the Gaia RR Lyrae at 37 arcsec and SPICY 43146 at 33 arcsec are the same objects earlier reviewers found. Result: Nothing within 30 arcsec in any table. Within 1 arcmin: SPICY 43146 (Class III, group G341.1-0.3) at 33.3 arcsec; Gaia DR3 5964332646302546560 (RR) at 37.2 and 5964332543223328000 (LPV) at 58.0; VIVACE 1116770 (EA/EB) at 53.6. Within 10 arcmin: 76 SPICY YSOs (nearest Class I SPICY 43108 at 113 arcsec, 43213 at 117); Contreras Pena 2017 VVVv356 at 157, VVVv357 at 250, VVVv353 at 366; Albarracin Mira d070_114_6668 at 81; ASAS-SN-V J165247.64-443744.8 at 178; SPICY-WISE-variable J165250.41-443908.4 (Class I) at 117; ATLASGAL 341.181-00.277 (NEOWISE-variable table) at 593; 103-109 Gaia DR3 variables. Within 1 degree: GCVS 8 stars (nearest V889 Sco at 20.8 arcmin; the only nova is V1662 Sco (2018) at 44.6 arcmin), NSV 3 (nearest NSV 8032 at 31.6 arcmin), 36 Contreras Pena 2017 VVV variables, Teixeira+2018 massive-YSO variables G341.20-0.26 at 11.5 arcmin. Empty to 1 degree: Lucas+2017 tables, Contreras+2017 spectroscopy, Contreras+2019, Contreras+2020, V4 tables, VVV LPV tables, RMS YSO NEOWISE, Park+2021, SPRITEs, Saito 2013 VVV novae, Shafter 2017, Pagnotta 2014, Ritter-Kolb, Downes CVs. Raw JSON is in recheck/B/dl/viz/.
- **vsnet-alert public archive** (2026-11-15 07:09:11 (list); 07:12:02-07:13:17 (32 bodies)). Control: The 2025 classical nova TCP J17301230-2753488 (AT 2025wyg) and MAXI J1750-327 appear, with coordinates parsed from the subjects. Result: 159 messages. Events in Scorpius and neighbouring constellations, with distance from B: V478 Sco (dwarf-nova activity, 2026-05-21) 11.1 deg; HP Nor (outburst) 11.4; IK Nor (active) 11.5; AS 221 (possible symbiotic nova, 2025-11-10, 17:12:12.9 -32:37:47) 12.6; V390 Sco (= 'SCOV390', Mira brightening, 2026-08-25) 13.5; MAXI J1750-327 (X-ray nova, 2026-08-17) 16.2; TCP J17301230-2753488 = AT 2025wyg (classical nova, Oph, 2025-09-07) 18.4; NSV 11274 (Tel) 19.7; ASASSN-26dv (Cen) 23.4; MASTER OT J142023.47-485540.0 (Lup) 26.1; TCP J16271026-1030020 (Oph) 34.6; ASASSN-26ew (Sgr) 34.9. Everything else is 35 to 175 deg away. Nothing in Scorpius within 11 deg.
- **MAXI flash reports / novae list** (2026-11-15 07:12:41). Control: MAXI J1750-327 (2026-08-13) is listed. Result: 2,002 entries (2010-02 to 2026-11-10), 161 of them since 2025-08-01. Nearest to B: type-I bursts from 4U 1705-440 at 2.4-3.3 deg; 4U 1630-472 at 4.2; GX 339-4 at 4.4-5.2; MAXI J1609-487 (2026-10) at 8.2-8.5. No new transient within 2 deg.
- **Fermi-LAT detected novae (K. Mukai, NASA GSFC)** (2026-11-15 07:13:08). Control: V462 Lup and V7994 Sgr are listed. Result: 2025-26 entries: V462 Lup, 'V572 Vul' (as written), V7994 Sgr, V1935 Cen, Fermi J1820-1648 (Feb 2026), V8056 Sgr (Oct 2026). None is in Scorpius, and none is close to B: the nearest Sgr/Cen positions are more than 15 deg away.
- **British Astronomical Association VSS: forum topic list (8 pages) and circulars VSSC 205-209 (Sep 2025 to Sep 2026)** (2026-11-15 07:16:56-07:18:02). Control: The Nova Sge 2026 and Nova Aql 2026 threads were found. Result: 2025-26 Galactic nova topics: Nova Sagittae 2026 (V488 Sge), Nova Aql 2026, Nova Tau 2026, and the recurrent-nova candidate AT2026lck (18:43:58.56 +01:52:48, about 55 deg away). The circulars mention only long-known Scorpius variables (V598 Sco, AR Sco, V1309 Sco). Nothing near B.
- **Guo et al. 2024 (MNRAS 528, 1769), arXiv HTML** (2026-11-15 07:23:34). Control: VVV1640-4846 is parsed with its catalogued position. Result: Nearest source: L222_59 (Lucas 2024 no. 59) at RA 253.43487 Dec -43.47205, 73.1 arcmin from B. This is the position of VVV-WIT-13 (RA 16:53:44.38 Dec -43:28:19.47 per arXiv 2509.15334). Next: VVV1636-4744 at 248.5 arcmin and VVV1640-4846 at 277.9.
- **Open-web searches (WebSearch)** (2026-11-15 07:14-07:21). Control: The same searches surfaced V1725 Sco, V1723 Sco, VVV-WIT-13 and the Karambelkar et al. 2026 SPHEREx transient paper. Result: No page about this source or position. The newest Scorpius nova designation found is V1725 Sco (2024); nothing exists for V1726-V1728 Sco. One Russian forum comment says 'Nova Scorpii 2025' (John Seach), but no position is given and it most likely refers to V1935 Cen; Mukai's list has no 2025 Scorpius nova. The arXiv hits are unrelated: an M31 red nova, a T CrB eruption-timing paper and the SPHEREx instrument paper.

Second round, partly:

- **Wikipedia list of novae** (2026-11-15 07:15:48). Control: V462 Lup is listed. Result: 2025: V462 Lupi, V572 Velorum, V1935 Centauri. No 2026 entries. The list holds only bright novae, so it is weak evidence for a faint infrared event.
- **VSOLJ** (2026-11-15 07:16:26). Control: No 2025-26 content exists to test against. Result: The site is 'under construction'; the last Variable Star Bulletin is No. 121 (2023 Jul). There is no 2025-26 nova or transient news. The observation-search CGI is a form and was not used.
- **Lucas et al. 2024 (MNRAS 528, 1789), open-access PDF at UCL Discovery** (2026-11-15 07:21:54). Control: VVV 1640-4846 is found in the text. Result: The printed Table 1 shows only 10 of its 222 rows; the full table is in the OUP online supplement. Of the 21 VVV J-names in the text, the nearest is VVV J163637.94-474444.1 at 4.1 deg.

First round (earlier ruling), with controls:

- TNS at 60 arcsec and 60 arcmin: only 2023 Gaia alerts within 1 deg.
- CBAT TOCP to 13 Nov 2026: the nearest entry is V1662 Sco, 44.6 arcmin away.
- Mukai: the nearest 2025-26 nova is 15.3 deg away.
- VSX, live and the 2026-10-18 copy: nothing within 37 arcsec.
- ASAS-SN transients: the nearest is 44.6 arcmin away.
- A VizieR all-catalogue 30-arcsec cone and about 40 catalogues within 33 arcsec: nothing.
- ATel titles 16940-18156 (1,217 telegrams): none about this place.
- Karambelkar et al. 2026 and Li, Wang & Lin 2026: they list other positions.

#### Candidate C (Norma)

Earlier report found: **no**.

Second round, each search with a passing control:

- **VizieR CfA mirror: VVV/VVVX eruptive and high-amplitude variable catalogues** (2026-11-15T07:15-07:16Z). Control: For each catalogue, a member (the nearest one to C, or any member when none lay within 10 deg) was found at 0.0 arcsec by the same 60-arcsec query at its own position, e.g. VVVv231, VVVv235 and VIVACE 1221624. Result: Rows within 1 arcmin / 10 arcmin / 1 deg: - 465/3011: 0 / 0 / 16; nearest VVVv231 (LPV-Mira, Ks amplitude 2.05) at 14.7 arcmin; also VVVv658 (Eruptive) at 19.0 arcmin. - 465/3039: 0 / 0 / 3; nearest VVVv235 (AGB) at 31.2 arcmin. - 472/2990: 0 / 0 / 0. - 486/4590: 0 / 0 / 0. - VIVACE: 2 / 167 / 7,265; nearest VIVACE 1221624 (EW, P 0.637 d) at 15.46 arcsec. - V4: 0 / 0 / 0. - A41: 0 / 0 / 1 (EGO G329.61+0.11 at 49.6 arcmin).
- **VizieR CfA mirror: SPICY and YSO-variability catalogues** (2026-11-15T07:16Z). Control: SPICY 32946 found at 0.0 arcsec by the same query; each other catalogue's member also found at 0.0 arcsec. Result: Rows within 1 arcmin / 10 arcmin / 1 deg: - SPICY: 0 / 33 / 1,261; nearest SPICY 32946 (Class II, SSTGLMC G330.4036-00.1023) at 81.5 arcsec, then SPICY 32927 at 188 arcsec. - 278/10: 0 / 3 / 163; nearest at 5.8 arcmin. - 281/64: 0 / 0 / 3; nearest at 28.3 arcmin. - 920/132: 0 / 0 / 0.
- **VizieR CfA mirror: Gaia DR3 variability (I/358, all tables)** (2026-11-15T07:18Z). Control: Science-alerts member at 243.56549 -52.48171 found at 0.0 arcsec by the same query. Result: Within 1 arcmin: one source, Gaia DR3 5933349095879173504 (class RS) at 11.95 arcsec. Within 10 arcmin: 116 in vari_summary (nearest RM at 102 arcsec, LPV at 157 arcsec, EB at 248 arcsec, a Cepheid at 535 arcsec). Within 1 deg: 7,854. Every class is periodic, LPV or rotation; none is an outburst.
- **VizieR CfA mirror: ASAS-SN variable stars (II/366)** (2026-11-15T07:17Z). Control: Nearest member found at 0.00 arcsec. Result: 0 / 12 / 292 within 1 arcmin / 10 arcmin / 1 deg. Nearest ASASSN-V J160654.36-520813.2 (ROT:, 0.06 mag) at 4.17 arcmin; also YSO-type entries at 5.3 and 6.8 arcmin.
- **VizieR CfA mirror: GCVS and NSV (B/gcvs)** (2026-11-15T07:17Z). Control: V345 Nor found at 0.00 arcsec, and NSV 07429 at 0.2 arcsec. Result: Within 1 arcmin: 0. Within 10 arcmin: V345 Nor (Mira, = NSV 07429) at 7.76 arcmin and V496 Nor (SR:) at 9.88 arcmin. Within 1 deg: 9 GCVS and 5 NSV entries, among them TW Nor (DCEP) at 23.3 arcmin and QX Nor (X-ray nova 1977, XND) at 55.5 arcmin. No 2025-26 designation.
- **VizieR CfA mirror: AAVSO VSX (B/vsx, version 2026-10-18)** (2026-11-15T07:17Z and 07:31Z). Control: V462 Lup found by a 60-arcsec cone at its position (227.01363 -40.14308). The 2026 novae V419 Mus and V2104 Aql are found by name, so the snapshot holds 2025-26 objects. Result: Within 1 arcmin: only Gaia DR3 5933349095879173504 (RS) at 11.99 arcsec. Within 10 arcmin: 120 rows. Within 1 deg: 7,731 rows, with no nova type and no name containing 2025/2026, TCP, PNV, ASASSN-25/26 or Gaia25/26. The nearest CV-type entries are Gaia19dsc (UG:) at 35.9 arcmin and Gaia21buw (UG:) at 56.9 arcmin. The highest Norma designation is V567 Nor (a nova, 7.03 deg away); no new Norma name was assigned in 2025-26. The Norma novae V555, V556, V559 and V567 Nor lie 1.74-7.03 deg away.
- **VizieR CfA mirror: nova catalogues** (2026-11-15T07:17-07:18Z). Control: Members found at 0.00 arcsec, e.g. V382 Nor at 244.93642 -51.58142 and the nova at 243.4291 -52.6226. These catalogues predate 2025. Result: 0 rows within 1 deg in every one.
- **VizieR CfA mirror: eROSITA Galactic X-ray transients (J/MNRAS/544/885)** (2026-11-15T07:18Z). Control: Member at 239.38758 -48.58603 found at 0.000 arcsec. Result: 0 rows within 1 deg.
- **vsnet-alert public archive** (2026-11-15T07:21:32Z (list); bodies 07:23Z). Control: V462 Lup appears as 'ASASSN-25cm - 8.7 mag transient in Lupus' (msg 28074, 2025-06-14, just before the window), and V572 Vel's PNV J10251200-5331109 decodes. vsnet-alert is incomplete for novae: V7994 Sgr and V1935 Cen have no subjects. Result: 159 messages (vsnet-alert 28093-28251), 83 with decodable coordinates. Nearest decoded position: TCP J17301230-2753488 = V4371 Oph (new classical nova, 2025-09-07) at 28.85 deg. Norma and its neighbours: - HP Nor, dwarf-nova outburst at 13.2 mag, 2026-05-21 (msg 28171): 3.39 deg; - IK Nor, 'active', the same digest: 4.17 deg; - MASTER OT J142023.47-485540.0, outburst 2026-05-21: 17.1 deg; - ASASSN-26dv, in Lupus: 18.1 deg; - V478 Sco: 21.8 deg; - AS 221 (Sco), possible symbiotic nova, 2025-11: 22.9 deg; - V390 Sco brightening, 2026-08: 24.0 deg; - NN Cen: 24.8 deg; - MAXI J1750-327, X-ray nova 2026-08: 27.0 deg; - V803 Cen: 29.3 deg. Nothing at C.
- **MAXI news and source list** (2026-11-15T07:26:06-07:26:34Z). Control: The same pages list MAXI J1750-327 (2026-08-13) and GS 1354-64 (2025-12-25), the 2025-26 X-ray transients also reported elsewhere (vsnet-alert 28209). Result: Two Norma events in 2025-26: (a) 2025-12-19: an X-ray transient in Norma, which NuSTAR (Dec 26-28) confirmed as the black-hole binary MAXI J1543-564 in outburst again (235.823 -56.414, 5.43 deg from C); (b) 2026-10-28: the new X-ray nova MAXI J1609-487 in Norma (242.237 -48.765, 3.46 deg from C), 380-530 mCrab, rebrightened Oct 31. The nearest MAXI source of any kind is 4U 1608-52 (QX Nor) at 0.93 deg. Nothing within MAXI's error of C (about 0.1-0.2 deg).
- **Fermi-LAT detected novae (Mukai)** (2026-11-15T07:25:02Z). Control: V462 Lup is present. Result: 2025-26 entries: V462 Lup, V572 Vel (printed 'V572 Vul'), V7994 Sgr, V1935 Cen, Fermi J1820-1648 (Feb 2026) and V8056 Sgr (Oct 2026). None in Norma; the nearest, V1935 Cen, is 14.2 deg away.
- **AAVSO forum, Alerts category** (2026-11-15T07:31Z). Control: 'Mag 8.7 transient in Lupus - rising nova?' = V462 Lup. Result: No Norma topic. The Southern ones are 'Mag 8.7 transient in Lupus', 'Nova in Centaurus', 'Possible Nova in Sagittarius', 'Nova Sgr 2026 No. 3' and 'Possible Bright Transient in Musca'.
- **Wikipedia** (2026-11-15T07:25:17Z and 07:25:54Z). Control: V462 Lup is listed. Result: 2025 entries: V462 Lup, V572 Vel and V1935 Cen (the list holds only bright novae); none for 2026; no Norma nova after IM Nor (2002).
- **Central Bureau (CBAT) public lists** (2026-11-15T07:25:01Z and 07:32Z). Control: V7994 Sgr (CBET 5612) and V1935 Cen are present. Result: nova_list.html is stale (its last entries are from 2010), so it is not evidence. CBET titles from 2025-08 to 2026-11 for Galactic novae: V4371 Oph (CBET 5603), V1935 Cen (5611), V7994 Sgr (5612, 5615), V419 Mus (5690, 5703), V2104 Aql (5711), V1452 Tau (5723), V8055 Sgr (5724), V488 Sge (5729) and V8056 Sgr (5763). None in Norma; the nearest, V1935 Cen, is 14.19 deg away. CBET texts are behind a subscription.
- **Open-web name searches (WebSearch, with astronomerstelegram.org and ADS domains excluded)** (2026-11-15T07:30-07:37Z). Control: 'Nova Lupi 2025' returns V462 Lup pages, and 'TCP J18035290-3127298' returns the CBAT and AAVSO pages for V7994 Sgr. Result: No page mentions this position or a nova or transient in Norma in 2025-26. The hits were unrelated objects: CX330 (a different, bulge object), IM Nor, AT 2026rdg in Aquila (TNS AstroNote 2026-233, read: a reddened Fe II nova in Aquila) and Nova Sgr 2026 No. 3. Search engines index catalogues and telegrams poorly, so this evidence is weak.

Second round, partly:

- **SIMBAD TAP mirror at IDIA (South Africa; listed by CDS)** (2026-11-15T07:03:59Z). Control: FAILED. V462 Lup is not found by the same cone or by name, and neither is V7994 Sgr (cone and ident LIKE searches). The mirror has 2026 references and some AT 2025 objects but not the 2025 Galactic novae. Its silence is therefore not evidence. Result: 2 arcmin: 6 objects. Nearest is HIGALBM G330.4120-00.0823 (smm) at 3.65 arcsec; then 2MASS J16064227-5211540 at 77 arcsec, SPICY 32946 at 81 arcsec, two dark clouds at 83 and 111 arcsec, and TYC 8322-377-1 at 87 arcsec. 30 arcmin: 2,372 objects, with no nova, CV, transient or 'ev' object. The most notable are an X-ray source 1RXS J160810.2-520251 (15.5 arcmin), EXMS B1605-522 (24.4 arcmin), PSR J1605-5215 (14.4 arcmin), the V* 2MASS J16064466-5203014 (9.35 arcmin) and the Mira V345 Nor (7.76 arcmin).
- **SIMBAD TAP mirror at CfA (simbad.cfa.harvard.edu; CDS says data are ingested up to 2026-10-14)** (2026-11-15T07:04:19Z). Control: FAILED: V462 Lup is not found by the same cone. Result: 2 arcmin: 7 rows, nearest HIGALBM G330.4120-00.0823 at 3.65 arcsec. 30 arcmin: 2,566 rows, no transient.
- **VizieR catalogue identification** (2026-11-15T07:06-07:14Z). Control: The registry search returned the known SPICY and VSX IDs, and -meta on the mirror confirmed each title. Result: (a) is broken on the mirrors: a Postgres 'syntax error at or near COMMIT' whenever more than one catalogue matches. The CDS original is down, and the NAOJ, IUCAA, INASAN and Cambridge mirrors time out. (b) gave the IDs: J/MNRAS/465/3011 and J/MNRAS/465/3039 (Contreras Pena+ 2017), J/MNRAS/472/2990 (Lucas+ 2017, eruptive YSOs), J/MNRAS/486/4590 (Contreras+ 2019), J/MNRAS/509/2566 (VIVACE), J/ApJ/864/11 (VVV V4), J/A+A/619/A41, J/ApJS/254/33 (SPICY), J/ApJS/278/10, J/ApJS/281/64, J/ApJ/920/132, I/358 (Gaia DR3 variability), II/366 (ASAS-SN variables), B/gcvs (GCVS + NSV), B/vsx, and the nova catalogues J/A+A/554/A123, J/ApJ/788/164, J/ApJ/834/196, J/MNRAS/517/6150, J/PAZh/34/270, J/ApJ/912/19, J/ApJ/910/134 and J/ApJS/197/31, plus J/MNRAS/544/885 (eROSITA Galactic X-ray transients). Lucas et al. 2024 (MNRAS 528, 1789) and Guo et al. 2024 (MNRAS 528, 1769) are NOT in VizieR: 'Table or Catalog not found' for J/MNRAS/528/1789 and 1769, and absent from the registry.
- **Lucas et al. 2024 and Guo et al. 2024 (VVV eruptive YSOs), not in VizieR** (2026-11-15T07:35Z). Control: Known members decode to their positions (VVV1640-4846 = VVV J164011.76-484653.4). Result: Guo et al. 2024 (2401.14464): 33 positions, nearest L222_33 (Eruptive) at 1.16 deg, then L222_32 at 2.21 deg and L222_37 at 2.80 deg. Lucas et al. 2024 (2401.14471): only part of the 222-object list carries positions in the HTML; nearest parsed is VVV J164011.76-484653.4 at 6.31 deg. Neither paper mentions G330.4.
- **Swift/BAT Hard X-ray Transient Monitor list** (2026-11-15T07:37Z). Control: None checked for a 2025-26 object. The list does contain the known Norma sources. Result: Nearest source H 1608-522 at 0.92 deg; then IGR J16207-5129 at 2.26 deg and H 1553-542 at 2.59 deg. No Swift J or new source within 2 deg.
- **AAVSO observing campaigns (the successor of Alert Notices)** (2026-11-15T07:27:44-07:30Z). Control: V462 Lup (#896) is present. Result: 2025-26 nova campaigns: V7993 Sgr, V462 Lup (#896), PNV J10251200-5331109 (#897), V4371 Oph (#905), V1935 Cen (#906) and V7994 Sgr (#907). The concluded campaigns from 2025-10 to 2026-08 include none in Norma. No campaign is in or near Norma.

First round (earlier ruling), with controls:

- TNS at 60 arcsec and 1 deg: nothing from 2025-26 within 1 deg. The nearest entry of any year is AT 2022oyv, 0.37 deg away.
- VSX: no nova among the 7,729 objects within 1 deg.
- VizieR all-catalogue cones of 12 and 60 arcsec: no variability entry.
- CBAT TOCP and Mukai: the nearest is V556 Nor (2018), 1.74 deg away.
- ASAS-SN transients: the nearest is 0.87 deg away.
- ATel titles and opening lines of 847 telegrams: none within 5 deg.
- Karambelkar et al. 2026, Li, Wang & Lin 2026 and Li & Wang 2024: the nearest listed object is 2.67 deg away.


## (b) The telegram check

Made after the wider search, at the team lead's request, by an automated reader of the site (an AI agent). It
is kept here as written; only its headings are one level lower. The site's search form logged the six searches
of step 1 at 08:04:53 to 08:05:25 UTC (`docs/sweep/vetting/atel_by_hand/searches.json`), and the account was
saved at 08:55 UTC; the "about 08:50 to 09:10 UTC" in its first line is its own estimate. Where it says
`vet2/A/reports`, read `docs/sweep/vetting/A/reports/` (a selection of those files was copied there).

### The Astronomer's Telegram check, 2026-11-15 (about 08:50 to 09:10 UTC)

Asked for by the team lead ("Go do that for astronomers telegram"). Reading only; nothing was
submitted. The site's robots.txt allows automated reading ("User-Agent: * Allow: /", and it names
Claude's agents as allowed); its "please confirm you are not a robot" page appears after many
page reads in a row, and it was never shown during this check.

#### What was done

1. **The site's own archive search form** (POST to https://www.astronomerstelegram.org with
   ListCriteria=Archive, June 2025 to December 2026, KeySearch=Yes, Boolean=Any), six words, six
   seconds apart. It is a full-text search (a search for "Sgr" earlier returned telegrams whose
   title does not contain it).

   | Word | Telegrams | What they are |
   |---|---|---|
   | V7994 (control) | 1 | 17419, Fermi-LAT detection of the nova V7994 Sgr: the search works |
   | Scorpius | 0 | |
   | Sco | 1 | 18155, a batch of spectroscopic classifications of optical transients: unrelated |
   | Seach | 1 | 18127, dust in the nova V572 Vel from SPHEREx (V572 Vel was found by J. Seach) |
   | Norma | 1 | 18134, spectroscopy of the comet 3I/ATLAS: unrelated |
   | Nor | 1 | 18134 again |

   Earlier the same night a reviewer ran, through the same form: SPHEREx (2: both about V572 Vel,
   17601 and 18127), Sgr (8), Sagittarius (1: 17995), infrared transient, WINTER, PGIR, Gattini,
   PRIME, VVVX, VVV, NEOWISE, FUor, YSO, eruptive, reddened, embedded, M20, W28, Trifid. The words
   "18:03" and "18 03" return every telegram (the form does not search punctuation), so they tell
   nothing.

2. **Every telegram from June 2025 to 14 November 2026 (numbers 17215 to 18156, 942 telegrams).**
   From the title index and the site's own per-telegram feed (title and opening sentences) that
   the reviewers had saved, every sky position and every coordinate-style name (J-names, TCP, PNV,
   MAXI J..., sexagesimal and decimal positions) was extracted: 263 in 150 telegrams. Distance of
   the nearest to each candidate:

   | Candidate | Nearest | Distance |
   |---|---|---|
   | A | XTE J1810-197 (telegrams 18039, 18040), a known magnetar | 4.0 degrees |
   | B | CXOU J164710.2-455216 (17311, 17312, 17322, 17599), a known magnetar | 1.5 degrees |
   | C | PMN J1603-4904 (17239, 17307, 17410, 17439), a known active galaxy | 3.2 degrees |

3. **The telegrams that give no position in their title or opening sentences but looked relevant.**
   Positions taken from the telegrams themselves as indexed by a web search engine:

   | Telegram | Object | Position (J2000) | From A |
   |---|---|---|---|
   | 17743 (2026-04-07) | PRIME26aaabsh, nova, about 10 arcmin from the Galactic centre | 17:46:20.70 -29:04:18.81 | 6.76 degrees |
   | 17945 (2026-08-06) | PRIME26ahygn, nova, first flagged 2026-03-28 at H 11.1, H 13.6 by 2026-08-05 | 17:42:10.63 -25:24:57.89 | 5.17 degrees |
   | 17426 (2025-09-30) | PRIME25aaghjd, symbiotic nova, about 1.1 degrees from the Galactic centre | not obtained | about 6 degrees or more (the centre is 6.79 degrees from A) |

   PRIME26ahygn resembles candidate A in date and brightness (A: first seen by SPHEREx 2026-03-20,
   about 23 to 36 mJy at 1.1 to 1.65 micrometres in spring 2026, near zero there by August), which
   is why its position was checked: it is 5.2 degrees away and is a different object. These three
   show that dust-hidden novae are being found toward the bulge in the near infrared by a survey
   that does not cover A's place.

4. **The telegrams the wider search had listed for a person to open**, by their names or the
   positions in their opening sentences:

   | Telegrams | Object | Distance |
   |---|---|---|
   | 17688, 17689, 17698, 17700 | Fermi J1820-1648 | 7.7 degrees from A |
   | 17989, 17995 | TCP J18251276-2225293 (nova) | 5.2 degrees from A |
   | 18122 | V8056 Sgr = TCP J17541876-2736362 (nova, found 2026-10-12) | 4.6 degrees from A |
   | 17552, 17559, 17560, 17569 | MAXI J1543-564 (235.818, -56.4115) | 5.4 degrees from C |
   | 17963, 17971, 17974 | MAXI J1750-327 (267.736, -32.734) | 9.7 degrees from A, 27 from C |
   | 18123, 18136 | MAXI J1609-487 (about 242.25, -48.7) | 3.5 degrees from C |

#### What it shows

No telegram found by any of these routes reports anything at or near candidate A, B or C.

#### What it does not cover

A telegram that reports something at one of the three places without the constellation's name or
abbreviation, without "SPHEREx", and without a position or coordinate-style name in its title or
opening sentences. A person reading through the 2025-26 nova and infrared-transient telegrams in
full, or NASA ADS, would close that gap. The team lead ran the ADS control (bibstem:ATel
abs:V7994 found telegram 17419) and the Sagittarius search by hand on 2026-11-15; the two results
he opened (18138, V488 Sge, in Sagitta; 18122, V8056 Sgr) are not candidate A.

Sources: https://www.astronomerstelegram.org/?read=17743 , ?read=17945 , ?read=17426 ; the site's
archive search form; the title index and per-telegram feed saved under vet2/A/reports,
vet2/B/reports and vet2/C/reports.

## (c) What has NOT been searched

Each item is from the wider search's lists (`still_unchecked`, `not_searched`) and from the telegram check, as
of 2026-11-15.

**For all three:**

- **The Astronomer's Telegram, read in full by a person.** The first round read titles and opening lines only
  (942 telegrams for A, 1,217 for B, 847 for C). The telegram check (b) then searched the full text by keyword
  through the site's own form and read every position in the titles and opening sentences of the 942 telegrams
  of June 2025 to 14 November 2026. What that does not cover, in its own words: "A telegram that reports something
  at one of the three places without the constellation's name or abbreviation, without "SPHEREx", and without a
  position or coordinate-style name in its title or opening sentences." Searching "18:03" and "18 03" in the form
  returns every telegram, so it tells nothing.
- **NASA ADS.** Only its control and one search for Sagittarius have been made by a person (see (b) and (d),
  step 2). The searches for SPHEREx, Scorpius and Norma have not.
- **SIMBAD at CDS.** It answered HTTP 404 at every try from 07:01 to 07:37 UTC (CDS reported a cybersecurity
  incident). The mirrors at CfA and IDIA answered but lack the 2025 control novae, so SIMBAD counts as not
  searched.
- **VizieR at CDS** was down as well; the CfA mirror was used instead, with controls.
- **CBET full texts** (a subscription). Only the public CBET titles were read.
- **The full tables of Lucas et al. 2024 (222 rows) and Contreras Pena et al. 2024.** They exist only as
  journal supplements; the publisher's page showed a robot check and the INAF copy needs a login.
- **The Transient Name Server and CBAT TOCP must be run again on the day of publication** (checklist step 4).
- **Searches that did not work** (no passing control, or the service did not answer), so they count as not
  searched: SIMBAD at CDS, VizieR at CDS, the CBAT public nova list (it stops in 2010), VSOLJ (last updated in
  2023), for B the AAVSO Alert Notices (HTTP 403, a robot check) and the OUP and INAF copies of Lucas et al.
  2024, and for C the BAA (no public alert list on its site; its alert archive is on groups.io, which was not
  opened). For C, the Swift/BAT transient list was read but had no 2025-26 control, so it counts as not
  searched.

**A:** AAVSO Alert Notices and Special Notices (not opened: aavso.org's robots.txt names Anthropic's crawlers
under "training crawlers"); the BAA forum thread "Nova Sagittarii 2026" (members only); TNS AstroNotes; the Fermi
FAVA gamma-ray light curve at A's place for September 2025 to March 2026 (a form); vsnet-outburst and vsnet-chat;
PRIME and WINTER internal lists. Loose ends: "Nova Sgr 2026 No. 1 and No. 2" were not matched by name, but every
confirmed 2025-26 nova on Mukai's list is at least 2.56 deg away; the saved copy of Mukai's unconfirmed list is
dated 12 Jan 2026.

**B:** AAVSO Alert Notices (a robot check, HTTP 403, not retried); Lasair (needs a token); VVV-WIT beyond
VVV-WIT-13; the VSOLJ search form. An unlocated forum comment about a "Nova Scorpii 2025" (John Seach) gives no
position; the searcher thinks it means V1935 Cen. The telegram check searched "Seach" and found only telegram
18127, about dust in the nova V572 Vel. Blind to this field: ZTF, Rubin/LSST brokers, KMTNet and MOA; Gaia alerts
ended in January 2025.

**C:** MAXI and Swift X-ray records were read only in part (MAXI with a control; Swift/BAT without one); the BAA
alert archive on groups.io; a few AAVSO campaign pages that served no text and page 2 of the concluded campaigns;
the full Li & Wang 2024 table; the forthcoming A&A paper aa60629-26 (its WISE data predate 2025); vsnet-outburst,
vsnet-chat and Lasair. Blind here: Gaia alerts (ended), ZTF, Fink/LSST, KMTNet, MOA and OGLE EWS.

## (d) The checklist for a person

This is the wider search's `checklist_for_a_person`, complete and word for word. The only additions are the
lines marked **Done:** after each check, where the date, the UTC time, what was typed and what came back are
written. Write the answers here: this section is the "'Searched' list" that the first paragraph speaks of, and
`docs/sweep.md` and `docs/sweep/report-draft.md` point here. Where a check has already been made, by a person or
by an automated reader, the line says so and by whom.

These checks only read pages. Do not submit, post or report anything while doing them. For each check, write down the date, the UTC time, what you typed and what came back, in the 'Searched' list for that candidate in docs/sweep.md.

Positions. Use these corrected positions, never the sweep's:
- A, in Sagittarius: RA 18:03:12.98, Dec -23:28:05.4 (decimal 270.80408, -23.46818).
- B, in Scorpius: RA 16:52:43.29, Dec -44:40:37.1 (decimal 253.18038, -44.67697).
- C, in Norma: RA 16:06:50.17, Dec -52:12:20.3 (decimal 241.70906, -52.20564).

How to judge a position you find in a report. All three declinations are negative.

'Same place' (within 30 arcsec):
- A: RA 18:03:10.8 to 18:03:15.2, and Dec -23:27:35 to -23:28:35.
- B: RA 16:52:40.5 to 16:52:46.1, and Dec -44:40:07 to -44:41:07.
- C: RA 16:06:46.9 to 16:06:53.4, and Dec -52:11:50 to -52:12:50.

'Nearby' (within 5 arcmin):
- A: RA 18:02:51 to 18:03:35, and Dec -23:23:05 to -23:33:05.
- B: RA 16:52:15 to 16:53:11, and Dec -44:35:37 to -44:45:37.
- C: RA 16:06:18 to 16:07:23, and Dec -52:07:20 to -52:17:20.

An X-ray or gamma-ray report gives a circle, called its 'error radius'. If our position falls inside that circle, count the report as 'nearby'.

1. The Astronomer's Telegram, full text. Nobody has searched it yet; the automated searches read only titles.
- Open https://www.astronomerstelegram.org/
- Control: type V7994 in its search box. The results must include ATel #17419, 'Fermi-LAT Gamma-ray Detection of the Nova V7994 Sgr'. If they do not, the search is not working: write that down and skip this step.

  **Done (control):** By a person: ____________ (date, UTC time, result).
  Since the checklist was written, an automated reader ran the site's own search form on 2026-11-15 at
  08:04:53 UTC: V7994 returned 1 telegram, 17419 (section (b)). That is not a person's check.

- Then type each of these, one at a time:
  - all candidates: SPHEREx;
  - A: Sagittarius, Sgr, 18:03, 18 03;
  - B: Scorpius, Sco, 16:52, 16 52, Seach;
  - C: Norma, Nor, 16:06, 16 06.

  **Done (all, SPHEREx):** By a person: ____________
  **Done (A):** By a person: ____________
  **Done (B):** By a person: ____________
  **Done (C):** By a person: ____________
  Already run by automated readers through the same form (section (b)): SPHEREx (2 telegrams, both about V572
  Vel: 17601 and 18127), Sgr (8), Sagittarius (1: 17995), Scorpius (0), Sco (1: 18155, unrelated), Seach (1:
  18127, about V572 Vel), Norma (1: 18134, unrelated), Nor (1: 18134 again). "18:03" and "18 03" return every
  telegram, because the form does not search punctuation, so they tell nothing. "16:52", "16 52", "16:06" and
  "16 06" were not run.

- Open every telegram dated 1 Aug 2025 or later about a nova, transient, outburst, young star or infrared source, and compare its position with the boxes.

  **Done:** By a person: ____________

- Also open each of these by number (https://www.astronomerstelegram.org/?read=17688 and so on) and check that its position is outside the boxes:
  - for A: 17688, 17689, 17698, 17700, 17743, 17945, 17989, 17995, 18122;
  - for C: 17552, 17559, 17560, 17569, 17963, 17971, 17974, 18123, 18136.

  **Done (A):** By a person: ____________
  **Done (C):** By a person: ____________
  The automated check took each one's object and position from its name or opening sentences, or from the
  telegram as a web search engine indexed it (17743, 17945). The nearest is 3.5 degrees from C (18123 and 18136,
  MAXI J1609-487) and 4.6 degrees from A (18122, V8056 Sgr): section (b), parts 3 and 4. A person has not opened
  them.

- Meaning: if nothing falls inside a box, write 'ATel: no report found'.

  **Result of step 1:** A: ____________ B: ____________ C: ____________

2. NASA ADS. Nobody has searched it yet.
- Open https://ui.adsabs.harvard.edu/ and type each line below into the search bar.
- Control: bibstem:ATel abs:V7994 must list 'Fermi-LAT Gamma-ray Detection of the Nova V7994 Sgr'. If it does not, write that down and skip this step.

  **Done (control):** 2026-11-15, by the team lead, by hand: bibstem:ATel abs:V7994 found telegram 17419. The
  time was not written down. (Recorded in section (b), "What it does not cover".)

- Then search:
  - abs:SPHEREx year:2025-2026
  - for A: bibstem:ATel year:2025-2026 abs:Sagittarius
  - for B: the same with abs:Scorpius
  - for C: the same with abs:Norma

  **Done (SPHEREx):** By a person: ____________
  **Done (A):** 2026-11-15, by the team lead, by hand: "the Sagittarius search". The two results he opened,
  18138 (V488 Sge, in Sagitta) and 18122 (V8056 Sgr), are not candidate A. The time, the exact words typed and
  the full list of results were not written down. Repeat it and write them here: ____________
  **Done (B):** By a person: ____________
  **Done (C):** By a person: ____________

- Read the title and abstract of every result about a transient, nova, outburst or infrared brightening, and compare any position given with the boxes.
- Meaning: if nothing falls inside a box, write 'ADS: no report found'.

  **Result of step 2:** A: ____________ B: ____________ C: ____________

3. SIMBAD at CDS. It was down all morning on 15 Nov 2026, and its mirrors are out of date.
- Control: open https://simbad.cds.unistra.fr/simbad/sim-id?Ident=V7994+Sgr . It must show a nova from 2025. If the page says it is unavailable, or shows no nova, try again another day.

  **Done (control):** ____________

- Then open:
  - A: https://simbad.cds.unistra.fr/simbad/sim-coo?Coord=270.80408+-23.46818&Radius=5&Radius.unit=arcmin
  - B: the same address with Coord=253.18038+-44.67697
  - C: the same address with Coord=241.70906+-52.20564
- What to expect:
  - A: nothing closer than 2MASS J18031598-2327530, about 43 arcsec away.
  - B: nothing closer than about 33 arcsec.
  - C: the cold dust cloud HIGALBM G330.4120-00.0823, about 4 arcsec away. It is a known cloud mapped by the Herschel telescope, not a report of a brightening.
- Meaning: any entry within 5 arcmin described as a nova, nova candidate, transient, outburst, eruptive star or cataclysmic star goes to the team.

  **Done (A):** ____________
  **Done (B):** ____________
  **Done (C):** ____________

4. On the day you publish, repeat two registry checks. Both found nothing on 15 Nov 2026.
- TNS:
  - Control: https://www.wis-tns.org/search?ra=227.01362&decl=-40.14308&radius=60&coords_unit=arcsec must list AT 2025nlr.
  - Then open https://www.wis-tns.org/search?ra=270.80408&decl=-23.46818&radius=300&coords_unit=arcsec for A, and the same address with ra=253.18038&decl=-44.67697 for B and ra=241.70906&decl=-52.20564 for C.
  - 'No results found' means nothing is registered within 5 arcmin.

  **Done (control):** ____________
  **Done (A):** ____________
  **Done (B):** ____________
  **Done (C):** ____________

- CBAT:
  - Open http://www.cbat.eps.harvard.edu/unconf/tocp.html , press Cmd-F (Ctrl-F on Windows) and type J1803 for A, J1652 for B and J1606 for C.
  - No hit means nothing is pending there. A hit whose declination part begins -23 (A), -44 (B) or -52 (C) goes to the team.

  **Done (A):** ____________
  **Done (B):** ____________
  **Done (C):** ____________

5. Optional: AAVSO. The automated searches were refused or held back there.
- Open https://www.aavso.org/apps/campaigns and https://www.aavso.org/apps/campaigns/archived .
- Look for any campaign since Aug 2025 on a nova or transient in Sagittarius, Scorpius or Norma, and compare its position with the boxes.

  **Done:** ____________

6. Optional, low priority: the Lucas et al. 2024 table. This needs journal access.
- Open the supplementary table at https://doi.org/10.1093/mnras/stad3929 , press Cmd-F and type J1803, J1652 and J1606.
- A name whose declination part begins -23 (A), -44 (B) or -52 (C) goes to the team.
- It is low priority because the VVV survey's catalogue lists only faint, steady stars near all three places.

  **Done:** ____________

If any check finds a report:
- Stop. Do not publish the 'no earlier report' sentence for that candidate.
- Save the page as a PDF or screenshot. Write down the report's name or number, its date, the position it gives and the uncertainty it states.
- Tell the team the same day. Any report found counts as earlier than ours, because the team has not reported anything anywhere.
- If it is inside the 'same place' box, treat the candidate as already reported. The page must name and cite that report and describe the SPHEREx data as an independent observation of it. Never call the object 'new' or 'first'.
- If it is inside the 'nearby' box, or our position is inside an X-ray or gamma-ray circle, it is a possible match. Ask a professional astronomer, for example the mentor, to compare the positions before anything goes public. Until then, the page says that a possibly related report exists and cites it.
- If steps 1-3 pass their controls and find nothing, the public sentence may drop the clause about sources not yet searched. It must keep 'this does not prove that no one else has seen it'.

### Before anything is filed

The checklist above is about searching. Filing a report is a separate decision, and it needs all three of these:

- [ ] Steps 1 to 4 above are done for all three candidates, and every answer is written in this file.
      Date: ____________
- [ ] The team agrees to report. Date: ____________
- [ ] A professional astronomer (for example a mentor) has checked the corrected positions and numbers.
      Date: ____________ (Write who checked only with their permission.)

Only then may anyone use part two of `docs/sweep/report-draft.md`.
