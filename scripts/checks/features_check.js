// Is every feature in one bar at the top, and does the Beginner | Expert switch at the bottom
// right change how everything is written?
// node features_check.js <playwright-core path> <base url> <out dir>
//
// The request this guards (the team lead, 14 Nov 2026): "where are the different features we are
// having, can you make a bar on top having all the features, so that toolbar will have all the
// features one by one, if you click on beginner mode toggle on the bottom right everything will
// be written in a way anyone can understand, and if you click on expert mode it will toggle to
// the nasa scientist mode".
const { chromium } = require(process.argv[2]);
const fs = require('fs');
const base = process.argv[3], out = process.argv[4];
fs.mkdirSync(out, { recursive: true });
let failed = 0;
const check = (ok, what) => { console.log(`${ok ? 'PASS' : 'FAIL'}  ${what}`); if (!ok) failed++; };

// The features, in the order of the bar, with the label each level shows.
const FEATURES = [
  { key: 'watch', beginner: 'Watch', expert: 'Viewer', kind: 'home' },
  { key: 'brightness', beginner: 'Brightness', expert: 'Light curve', kind: 'tool' },
  { key: 'spectrum', beginner: 'Colours', expert: 'Spectrum', kind: 'tool' },
  { key: 'search', beginner: 'Find changes', expert: 'Blind search', kind: 'tool' },
  { key: 'distant', beginner: 'Far-off planet', expert: 'Planet X search', kind: 'tool' },
  { key: 'smallbodies', beginner: 'Asteroids', expert: 'Small bodies', kind: 'tool' },
  { key: 'context', beginner: 'What is it?', expert: 'Object card', kind: 'tool' },
  { key: 'practise', beginner: 'Practise', expert: 'Training', kind: 'screen', address: /train=/ },
  { key: 'vote', beginner: 'Observe anomalies', expert: 'Anomalies', kind: 'screen', address: /watchlist=1/ },
  { key: 'tools', beginner: 'Three tools', expert: 'Methods', kind: 'screen', address: /tools=1/ },
];
// Words a newcomer must not meet in Beginner unless they sit inside a closed fold.
const BANNED = /\b(sigma|flux|fluxes|epoch|epochs|detector|detectors|centroid|centroids|mJy|aperture|photometry|ephemeris|S\/N)\b|σ/;

const barItems = () => {
  const nav = document.querySelector('nav[aria-label="Features"]');
  if (!nav) return null;
  const r = nav.getBoundingClientRect();
  return {
    top: r.top, bottom: r.bottom, left: r.left, right: r.right, scrollW: nav.scrollWidth, clientW: nav.clientWidth,
    items: [...nav.querySelectorAll('a, button')].map((el) => { const b = el.getBoundingClientRect(); return { text: (el.textContent || '').trim(), name: el.getAttribute('aria-label') || (el.textContent || '').trim(), current: el.getAttribute('aria-current'), tag: el.tagName, href: el.getAttribute('href') || '', left: b.left, right: b.right, top: b.top, bottom: b.bottom }; }),
  };
};
const dock = () => {
  const el = document.querySelector('[role="group"][aria-label="How much to show"]');
  if (!el) return null;
  let fixed = false;
  for (let e = el; e && e !== document.documentElement; e = e.parentElement) if (getComputedStyle(e).position === 'fixed') fixed = true;
  const r = el.getBoundingClientRect();
  const pressed = [...el.querySelectorAll('button')].find((b) => b.getAttribute('aria-pressed') === 'true');
  const overlaps = [];
  const hit = (sel, label) => { for (const o of document.querySelectorAll(sel)) { if (el.contains(o) || o.contains(el)) continue; const b = o.getBoundingClientRect(); if (b.width < 2 || b.height < 2) continue; const ox = Math.min(r.right, b.right) - Math.max(r.left, b.left); const oy = Math.min(r.bottom, b.bottom) - Math.max(r.top, b.top); if (ox > 1 && oy > 1) overlaps.push(label + ': ' + ((o.getAttribute('aria-label') || o.textContent || '').trim().slice(0, 24))); } };
  hit('.stage', 'the picture'); hit('.visit-strip', 'the visits');
  hit('main button, main a[href], main select, main input, main summary, aside button, aside a[href], aside select, aside summary', 'a control');
  return { fixed, right: window.innerWidth - r.right, bottom: window.innerHeight - r.bottom, w: r.width, h: r.height, pressed: pressed ? (pressed.textContent || '').trim() : null, overlaps: [...new Set(overlaps)] };
};
// The visible words of the open tool panels, leaving out what sits in a closed <details>.
const panelWords = () => [...document.querySelectorAll('.tool-slot')].map((slot) => {
  const clone = slot.cloneNode(true);
  clone.querySelectorAll('details:not([open]) > *:not(summary)').forEach((n) => n.remove());
  clone.querySelectorAll('[hidden], .sr-only, svg title, svg desc').forEach((n) => n.remove());
  return { id: slot.id, text: (clone.textContent || '').replace(/\s+/g, ' ').trim() };
});

async function setLevel(page, label) {
  const b = page.locator('[role="group"][aria-label="How much to show"] button', { hasText: new RegExp('^' + label + '$') });
  if (await b.count()) { await b.first().click(); await page.waitForTimeout(400); return true; }
  return false;
}

(async () => {
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const mode of ['beginner', 'expert']) {
    for (const [w, h] of [[1440, 900], [1280, 720], [390, 844]]) {
      const tag = `${mode} ${w}x${h}`;
      const page = await browser.newPage({ viewport: { width: w, height: h } });
      const errors = [];
      page.on('pageerror', (e) => errors.push(e.message.slice(0, 140)));
      await page.goto(`${base}/?ui=${mode}`);
      await page.waitForSelector('.stage img', { timeout: 120000 });
      await page.waitForTimeout(1200);

      // 1. The bar: at the top, every feature in order, written for this level.
      const bar = await page.evaluate(`(${barItems.toString()})()`);
      check(!!bar, `${tag}: there is a navigation bar named "Features"`);
      if (!bar) { await page.close(); continue; }
      check(bar.top >= 0 && bar.bottom <= 120, `${tag}: the bar is at the top of the page (from ${Math.round(bar.top)} to ${Math.round(bar.bottom)} px)`);
      const want = FEATURES.map((f) => f[mode]);
      const got = bar.items.map((i) => i.text);
      check(JSON.stringify(got) === JSON.stringify(want), `${tag}: the bar lists every feature in order, in this level's words${JSON.stringify(got) === JSON.stringify(want) ? '' : ` (shows: ${got.join(' | ')}; wanted: ${want.join(' | ')})`}`);
      if (w >= 1280) {
        const cut = bar.items.filter((i) => i.right > w + 0.5 || i.left < -0.5).map((i) => i.text);
        check(cut.length === 0 && bar.scrollW <= bar.clientW + 1, `${tag}: every feature is in view in the bar without scrolling it${cut.length ? ' (cut off: ' + cut.join(', ') + ')' : ''}`);
      } else {
        const sideways = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        check(sideways <= 1, `${tag}: the page does not scroll sideways (${sideways} px); the bar may scroll inside itself`);
      }
      check(bar.items.filter((i) => i.current && i.current !== 'false').length === 1, `${tag}: exactly one feature is marked as the current one`);
      const first = bar.items[0];
      check(!!first && !!first.current && first.current !== 'false', `${tag}: on arrival the current feature is "${want[0]}"`);

      // 2. The switch: fixed at the bottom right, covering nothing.
      const d = await page.evaluate(`(${dock.toString()})()`);
      check(!!d && d.fixed && d.right >= 0 && d.right <= 32 && d.bottom >= 0 && d.bottom <= 32, `${tag}: the Beginner | Expert switch is fixed at the bottom right${d ? ` (${Math.round(d.right)} px from the right edge, ${Math.round(d.bottom)} from the bottom, fixed: ${d.fixed})` : ' (not found)'}`);
      check(!!d && d.overlaps.length === 0, `${tag}: the switch covers no picture, visit or control${d && d.overlaps.length ? ' (covers ' + d.overlaps.slice(0, 4).join('; ') + ')' : ''}`);
      check(!!d && d.pressed === (mode === 'beginner' ? 'Beginner' : 'Expert'), `${tag}: the switch shows ${mode} as the level in use`);

      // 3. Each tool opens from the bar, at this level, in this level's words.
      for (const f of FEATURES.filter((x) => x.kind === 'tool')) {
        const item = page.locator('nav[aria-label="Features"] :is(a, button)', { hasText: new RegExp('^' + f[mode].replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$') }).first();
        await item.click();
        await page.waitForTimeout(900);
        const state = await page.evaluate(`[(${barItems.toString()})(), (${panelWords.toString()})()]`);
        const cur = state[0].items.find((i) => i.current && i.current !== 'false');
        check(!!cur && cur.text === f[mode], `${tag}: pressing "${f[mode]}" marks it as the current feature${cur ? '' : ' (nothing marked)'}`);
        const panel = state[1].find((p) => p.id === 'tool-' + f.key) || state[1][state[1].length - 1];
        check(!!panel && panel.text.length > 40, `${tag}: pressing "${f[mode]}" opens its panel${panel ? '' : ' (no panel found; panels on the page: ' + state[1].map((p) => p.id).join(', ') + ')'}`);
        if (panel && mode === 'beginner') {
          const m = BANNED.exec(panel.text);
          check(!m, `${tag}: the "${f[mode]}" panel uses no scientist's word outside a closed fold${m ? ` (found "${m[0]}" in: "…${panel.text.slice(Math.max(0, m.index - 40), m.index + 30)}…")` : ''}`);
        }
      }
      // 4. Back to the picture.
      await page.locator('nav[aria-label="Features"] :is(a, button)', { hasText: new RegExp('^' + FEATURES[0][mode].replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$') }).first().click();
      await page.waitForTimeout(900);
      const home = await page.evaluate(`[(${barItems.toString()})(), (() => { const r = document.querySelector('.stage').getBoundingClientRect(); return r.top >= -1 && r.top < window.innerHeight * 0.6; })()]`);
      const cur0 = home[0].items.find((i) => i.current && i.current !== 'false');
      check(!!cur0 && cur0.text === FEATURES[0][mode] && home[1], `${tag}: pressing "${FEATURES[0][mode]}" brings the picture back into view and marks it current`);

      // 5. The switch rewrites the bar.
      const other = mode === 'beginner' ? 'expert' : 'beginner';
      const switched = await setLevel(page, other === 'expert' ? 'Expert' : 'Beginner');
      const after = switched ? await page.evaluate(`(${barItems.toString()})()`) : null;
      check(!!after && JSON.stringify(after.items.map((i) => i.text)) === JSON.stringify(FEATURES.map((f) => f[other])), `${tag}: pressing ${other} on the switch rewrites the bar in ${other}'s words`);
      await setLevel(page, mode === 'expert' ? 'Expert' : 'Beginner');

      // 6. The other screens are in the bar, carry the same bar, and keep the level.
      const now = await page.evaluate(`(${barItems.toString()})()`);
      for (const f of FEATURES.filter((x) => x.kind === 'screen')) {
        const it = now.items.find((i) => i.text === f[mode]);
        check(!!it && (it.tag === 'A' ? f.address.test(it.href) : true), `${tag}: "${f[mode]}" is in the bar${it && it.tag === 'A' ? ' and leads to ' + it.href.slice(0, 40) : ''}`);
      }
      if (w === 1440) {
        for (const f of FEATURES.filter((x) => x.key === 'vote' || x.key === 'practise')) {
          await page.locator('nav[aria-label="Features"] :is(a, button)', { hasText: new RegExp('^' + f[mode].replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$') }).first().click();
          await page.waitForFunction(() => /train=|watchlist=1/.test(window.location.search), null, { timeout: 30000 }).catch(() => {});
          await page.waitForSelector('nav[aria-label="Features"]', { timeout: 60000 }).catch(() => {});
          await page.waitForTimeout(1200);
          const there = await page.evaluate(`[(${barItems.toString()})(), (${dock.toString()})(), window.location.search]`);
          const curS = there[0] ? there[0].items.find((i) => i.current && i.current !== 'false') : null;
          check(f.address.test(there[2]) && !!curS && curS.text === f[mode], `${tag}: the ${f.key} screen opens from the bar, shows the same bar and marks "${f[mode]}" current${curS ? '' : ' (bar or mark missing; address ' + there[2].slice(0, 40) + ')'}`);
          check(!!there[1] && there[1].pressed === (mode === 'beginner' ? 'Beginner' : 'Expert') && there[1].fixed, `${tag}: the ${f.key} screen keeps the switch at the bottom right with ${mode} in use`);
          await page.locator('nav[aria-label="Features"] :is(a, button)', { hasText: new RegExp('^' + FEATURES[0][mode].replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$') }).first().click();
          await page.waitForSelector('.stage img', { timeout: 120000 }).catch(() => {});
          await page.waitForTimeout(800);
        }
      }
      check(errors.length === 0, `${tag}: no script errors${errors.length ? ': ' + errors.slice(0, 2).join(' | ') : ''}`);
      await page.screenshot({ path: `${out}/features_${mode}_${w}.png` });
      await page.close();
    }
  }
  await browser.close();
  console.log(failed ? `\n${failed} FAILED` : '\nALL PASS');
  process.exit(failed ? 1 : 0);
})();
