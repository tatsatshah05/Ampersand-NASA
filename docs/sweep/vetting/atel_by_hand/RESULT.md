# The Astronomer's Telegram check, 2026-11-15 (about 08:50 to 09:10 UTC)

Asked for by the team lead ("Go do that for astronomers telegram"). Reading only; nothing was
submitted. The site's robots.txt allows automated reading ("User-Agent: * Allow: /", and it names
Claude's agents as allowed); its "please confirm you are not a robot" page appears after many
page reads in a row, and it was never shown during this check.

## What was done

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

## What it shows

No telegram found by any of these routes reports anything at or near candidate A, B or C.

## What it does not cover

A telegram that reports something at one of the three places without the constellation's name or
abbreviation, without "SPHEREx", and without a position or coordinate-style name in its title or
opening sentences. A person reading through the 2025-26 nova and infrared-transient telegrams in
full, or NASA ADS, would close that gap. The team lead ran the ADS control (bibstem:ATel
abs:V7994 found telegram 17419) and the Sagittarius search by hand on 2026-11-15; the two results
he opened (18138, V488 Sge, in Sagitta; 18122, V8056 Sgr) are not candidate A.

Sources: https://www.astronomerstelegram.org/?read=17743 , ?read=17945 , ?read=17426 ; the site's
archive search form; the title index and per-telegram feed saved under vet2/A/reports,
vet2/B/reports and vet2/C/reports.
