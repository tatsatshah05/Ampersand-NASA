// Do the words on the page hold still while the visits play, and is the catalogue check in view?
// node stilltext_check.js <playwright-core path> <base url> <out dir>
//
// The complaint this guards against (the team lead, 14 Nov 2026, with a screenshot of the Expert
// side column): "WHY IS THIS KEEPING ON CHANGING, IT IS NOT EVEN VISIBLE". The page plays through
// the visits by itself, and sentences that describe "the visit on screen" were rewritten about
// once a second, some of them 400 px below the bottom of the side column.
//
// THE RULE: while the visits play, no visible word changes. The picture changes, and a mark shows
// which visit is on screen. Words change only as the answer to something the visitor does.
const { chromium } = require(process.argv[2]);
const fs = require('fs');
const base = process.argv[3], out = process.argv[4];
fs.mkdirSync(out, { recursive: true });
let failed = 0;
const check = (ok, what) => { console.log(`${ok ? 'PASS' : 'FAIL'}  ${what}`); if (!ok) failed++; };

// Every visible word, in page order. Hidden text (display none, visibility hidden, the hidden
// attribute, a closed <details>) is left out, as innerText does. Text that is only clipped
// (the sr-only class) IS included: a screen-reader region that is rewritten while playing
// would also never stop talking.
const visibleText = () => document.body.innerText.replace(/[ \t]+/g, ' ').replace(/\n\s*\n+/g, '\n').trim();
// Which picture is showing. The page may swap the src of one <img> or stack one <img> per visit and show one.
const pictureNow = () => [...document.querySelectorAll('.stage img')].filter((i) => { const c = getComputedStyle(i); return c.visibility !== 'hidden' && c.display !== 'none' && Number(c.opacity) > 0.5; }).map((i) => i.getAttribute('src')).join(',');

const firstDifference = (a, b) => {
  const la = a.split('\n'), lb = b.split('\n');
  for (let i = 0; i < Math.max(la.length, lb.length); i++) if (la[i] !== lb[i]) return `"${(la[i] ?? '').slice(0, 90)}" became "${(lb[i] ?? '').slice(0, 90)}"`;
  return '';
};

// Watch the page for `ms` and report how many versions of its text and how many pictures were seen.
async function watch(page, ms) {
  const texts = new Set(), pictures = new Set();
  let first = null, change = '';
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    const [text, picture] = await page.evaluate(`[(${visibleText.toString()})(), (${pictureNow.toString()})()]`);
    if (first === null) first = text;
    if (!texts.has(text)) { texts.add(text); if (texts.size === 2) change = firstDifference(first, text); }
    pictures.add(picture);
    await page.waitForTimeout(150);
  }
  return { versions: texts.size, pictures: pictures.size, change };
}

async function ensurePlaying(page) {
  if (!(await page.getByRole('button', { name: 'Pause', exact: true }).count())) {
    const play = page.getByRole('button', { name: 'Play', exact: true });
    if (await play.count()) await play.first().click();
  }
  await page.waitForTimeout(400);
  return (await page.getByRole('button', { name: 'Pause', exact: true }).count()) > 0;
}

(async () => {
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const mode of ['beginner', 'expert']) {
    for (const [w, h] of [[1440, 900], [1280, 720]]) {
      const tag = `${mode} ${w}x${h}`;
      const page = await browser.newPage({ viewport: { width: w, height: h } });
      const errors = [];
      page.on('pageerror', (e) => errors.push(e.message.slice(0, 160)));
      await page.goto(`${base}/?ui=${mode}`);
      await page.waitForSelector('.stage img', { timeout: 120000 });
      await page.waitForTimeout(1500);

      // 1. While the visits play: the picture changes, the words do not.
      check(await ensurePlaying(page), `${tag}: the visits are playing for this test`);
      const played = await watch(page, 9000);
      check(played.pictures >= 2, `${tag}: the picture did change while playing (${played.pictures} different pictures seen)`);
      check(played.versions === 1, `${tag}: no visible word changed while the visits played (${played.versions} versions of the page's text in 9 s${played.change ? '; first change: ' + played.change : ''})`);

      // 2. The same with Blink first and last.
      // Blink is a toggle button with aria-pressed (an earlier version of this check looked for a checkbox and so never ran this part).
      // FINDER REPAIRED (15 Nov): a before-and-after view (Dev's candidates, the landing view) names it "Blink before and after".
      const blink = page.getByRole('button', { name: /^Blink (first and last|before and after)$/ });
      check((await blink.count()) === 1, `${tag}: the Blink button is found`);
      if (await blink.count()) {
        // FINDER REPAIRED (15 Nov): a before-and-after view (the landing candidate) already blinks when it
        // opens, so Blink is pressed only when it is not on yet (pressing it again would turn it off).
        if ((await blink.first().getAttribute('aria-pressed')) !== 'true') await blink.first().click();
        await page.waitForTimeout(600);
        check((await blink.first().getAttribute('aria-pressed')) === 'true', `${tag}: Blink is on for this test`);
        const blinked = await watch(page, 5000);
        check(blinked.pictures >= 2, `${tag}: the picture did change while blinking (${blinked.pictures} pictures)`);
        check(blinked.versions === 1, `${tag}: no visible word changed while blinking first and last (${blinked.versions} versions${blinked.change ? '; first change: ' + blinked.change : ''})`);
        await blink.first().click();
        await page.waitForTimeout(300);
      }

      // 3. Expert: the measured-against-catalogue comparison is in view without scrolling anything,
      //    and it covers every visit (so it need not be rewritten when the visit changes).
      if (mode === 'expert') {
        // FINDER REPAIRED (15 Nov): the page now opens on one of Dev's candidates, which no catalogue
        // predicts, so there is no measured-against-Gaia comparison on it. The comparison is looked for
        // where it exists, on Barnard's Star at the old landing address (Gaia's own star, no motion given), with the same rule.
        await page.goto(`${base}/?ui=${mode}&ra=269.446267&dec=4.768222&name=Barnard%27s+Star`);
        await page.waitForSelector('.stage img', { timeout: 120000 });
        await page.waitForTimeout(1500);
        const where = await page.evaluate(() => {
          const all = [...document.querySelectorAll('aside *')].filter((el) => {
            const t = el.textContent || '';
            return /Gaia/.test(t) && /predict/i.test(t) && /\d\s*(″|"|arcsec)/.test(t);
          });
          all.sort((a, b) => (a.textContent || '').length - (b.textContent || '').length);
          const el = all[0];
          if (!el) return null;
          const r = el.getBoundingClientRect();
          return { top: r.top, bottom: r.bottom, shown: r.width > 0 && r.height > 0 };
        });
        check(!!where && where.shown && where.top >= 0 && where.bottom <= h,
          `${tag}: the measured-against-Gaia comparison is inside the window without scrolling (${where ? `top ${Math.round(where.top)}, bottom ${Math.round(where.bottom)} of ${h}` : 'not found in the side column'})`);

        // 3b. Every button of the side column can be reached without scrolling it (1440x900 only).
        if (w === 1440) {
          const below = await page.evaluate((hh) => [...document.querySelectorAll('aside button, aside select, aside summary')].filter((el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.bottom > hh; }).map((el) => (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30)), h);
          check(below.length === 0, `${tag}: every control of the side column is inside the window without scrolling it${below.length ? ' (below the fold: ' + below.slice(0, 6).join('; ') + (below.length > 6 ? ` and ${below.length - 6} more` : '') + ')' : ''}`);
        }

        // 3c. With every fold of the side column open, the words still hold still while playing.
        await page.evaluate(() => document.querySelectorAll('aside details').forEach((d) => { d.open = true; }));
        await page.waitForTimeout(300);
        await ensurePlaying(page);
        const folds = await watch(page, 5000);
        check(folds.versions === 1, `${tag}: with every fold of the side column open, no word changed while playing (${folds.versions} versions${folds.change ? '; first change: ' + folds.change : ''})`);
      }

      // 4. Beginner: each "i" explanation holds still while the visits play behind it.
      if (mode === 'beginner') {
        const names = await page.evaluate(() => [...document.querySelectorAll('button[aria-expanded]')].map((b) => b.getAttribute('aria-label') || (b.textContent || '').trim()).filter((n) => /^About /.test(n)));
        for (const name of [...new Set(names)]) {
          await ensurePlaying(page);
          const button = page.getByRole('button', { name, exact: true }).first();
          await button.click();
          await page.waitForTimeout(300);
          const open = await watch(page, 3500);
          check(open.versions === 1, `${tag}: "${name}" open, no word changed while the visits played (${open.versions} versions${open.change ? '; first change: ' + open.change : ''})`);
          await page.keyboard.press('Escape');
          await page.waitForTimeout(150);
        }
      }

      // 5. Stepping by hand: a mark of the current visit follows.
      const pause = page.getByRole('button', { name: 'Pause', exact: true });
      if (await pause.count()) await pause.first().click();
      await page.waitForTimeout(300);
      const marks = new Set();
      for (let i = 0; i < 4; i++) {
        await page.getByRole('button', { name: /next/i }).first().click();
        await page.waitForTimeout(200);
        marks.add(await page.evaluate(() => [...document.querySelectorAll('[aria-current]:not([aria-current="false"])')].map((el) => (el.textContent || '').trim().slice(0, 40)).join(' | ')));
      }
      check(marks.size >= 2, `${tag}: stepping by hand moves the mark of the current visit (${marks.size} different states)`);

      // 6. Expert with a tool panel open: when the picture is scrolled out of sight the visits stop
      //    playing by themselves, and they start again when it comes back.
      if (mode === 'expert') {
        // The brightness tool: a feature of the bar at the top ('Light curve' in Expert), or, on older builds, a button of the side column.
        const inBar = page.locator('nav[aria-label="Features"] :is(a, button)', { hasText: /^(Light curve|Brightness)$/ });
        const tool = (await inBar.count()) ? inBar : page.getByRole('button', { name: 'Brightness over time', exact: true });
        if (await tool.count()) {
          await ensurePlaying(page);
          await tool.first().click();
          await page.waitForTimeout(1500);
          await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
          await page.waitForTimeout(900);
          const stageVisible = await page.evaluate(() => { const r = document.querySelector('.stage')?.getBoundingClientRect(); return !!r && r.bottom > 0 && r.top < window.innerHeight; });
          if (!stageVisible) {
            const away = await watch(page, 4000);
            check(away.pictures === 1, `${tag}: with the picture scrolled out of sight, the visits stop playing (${away.pictures} pictures seen in 4 s)`);
            await page.evaluate(() => window.scrollTo(0, 0));
            await page.waitForTimeout(700);
            const back = await watch(page, 4000);
            check(back.pictures >= 2, `${tag}: back at the picture, the visits play again without pressing anything (${back.pictures} pictures seen in 4 s)`);
          } else {
            console.log(`NOTE  ${tag}: the picture stays in sight with a tool panel open, so the scrolled-away check does not apply`);
          }
        }
      }
      check(errors.length === 0, `${tag}: no script errors${errors.length ? ': ' + errors.slice(0, 2).join(' | ') : ''}`);
      await page.screenshot({ path: `${out}/still_${mode}_${w}.png` });
      await page.close();
    }
  }
  await browser.close();
  console.log(failed ? `\n${failed} FAILED` : '\nALL PASS');
  process.exit(failed ? 1 : 0);
})();
