// The boxes that take a position say how to type one.
//
//   node scripts/checks/searchbox_check.js <playwright-core path> <base url> <out dir>
//
// At five window widths: the words in the empty search box are whole (never cut short). Clicked,
// the box says "A name, or right ascension and declination" whole (in a laptop window it widens
// to do so, without moving the form or the target buttons), and a card under it gives the order
// and both ways of writing a position; each example on the card, typed into the box, is read as
// coordinates. The box under "Pick a patch of sky" on Observe anomalies has the same instruction
// under it. Pictures of each go to the out dir. Prints one line per check and ALL PASS at the
// end, or the number that failed.
const [pw, base, out] = process.argv.slice(2)
if (!pw || !base || !out) {
  console.error('usage: node searchbox_check.js <playwright-core path> <base url> <out dir>')
  process.exit(2)
}
const { chromium } = require(pw)
const fs = require('fs')
fs.mkdirSync(out, { recursive: true })

let failed = 0
function check(ok, what) {
  if (!ok) failed += 1
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${what}`)
}

const ORDER = 'right ascension (RA) first, then declination (Dec)'

;(async () => {
  const browser = await chromium.launch()
  for (const width of [390, 1024, 1280, 1440, 1680]) {
    const page = await browser.newPage({ viewport: { width, height: 800 } })
    await page.goto(base, { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('.searchbar-input')
    // What the box says, whether it is whole, and where the form and the first target button are.
    const look = () =>
      page.evaluate(() => {
        const input = document.querySelector('.searchbar-input')
        const style = getComputedStyle(input)
        const pen = document.createElement('canvas').getContext('2d')
        pen.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`
        const place = (el) => {
          const r = el.getBoundingClientRect()
          return [r.left, r.top, r.width, r.height].map((n) => Math.round(n * 10) / 10).join(' ')
        }
        const row = document.querySelector('.searchbar-row').getBoundingClientRect()
        return {
          says: input.placeholder,
          wide: pen.measureText(input.placeholder).width,
          room: input.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight),
          // Chrome keeps 24 px free for the clear button even in an empty box, unless a rule takes
          // the button out while the box is empty (SearchBar.css). The room above counts on that rule.
          clear: [...document.styleSheets].some((sheet) =>
            [...sheet.cssRules].some((rule) => /:placeholder-shown::-webkit-search-cancel-button/.test(rule.selectorText ?? '') && rule.style.display === 'none'),
          ),
          form: place(document.querySelector('form.searchbar')),
          firstTarget: place(document.querySelector('.target')),
          inWindow: row.left >= 0 && row.right <= document.documentElement.clientWidth,
        }
      })
    const rest = await look()
    check(rest.wide <= rest.room && rest.clear, `${width} px: the empty box says "${rest.says}" whole (${Math.round(rest.wide)} of ${Math.round(rest.room)} px)`)
    await page.locator('.targets').screenshot({ path: `${out}/searchbox-rest-${width}.png` })

    await page.locator('.searchbar-input').focus()
    const card = page.locator('.searchbar-pop')
    await card.waitFor({ state: 'visible' })
    await page.waitForFunction(() => /right ascension and declination/.test(document.querySelector('.searchbar-input').placeholder), null, { timeout: 3000 }).catch(() => {})
    const used = await look()
    check(used.says === 'A name, or right ascension and declination' && used.wide <= used.room, `${width} px: clicked, the box says "${used.says}" whole (${Math.round(used.wide)} of ${Math.round(used.room)} px)`)
    check(used.inWindow && used.form === rest.form && used.firstTarget === rest.firstTarget, `${width} px: clicked, the box is inside the window, and the form and the first target button have not moved`)
    const words = (await card.innerText()).replace(/\s+/g, ' ')
    check(words.includes(ORDER), `${width} px: the card under the box gives the order: ${ORDER}`)
    check(/Both in degrees/.test(words) && /RA in hours, Dec in degrees/.test(words) && /J2000/.test(words), `${width} px: the card gives both ways of writing it and says J2000`)
    const within = await page.evaluate(() => {
      const r = document.querySelector('.searchbar-pop').getBoundingClientRect()
      return r.left >= 0 && r.right <= document.documentElement.clientWidth
    })
    check(within, `${width} px: the card is inside the window`)
    const top = (await page.locator('.targets').boundingBox()).y
    await page.screenshot({ path: `${out}/searchbox-card-${width}.png`, clip: { x: 0, y: Math.max(0, top - 8), width: Math.min(width, 760), height: 340 } })

    if (width === 1280) {
      const examples = await page.locator('.searchbar-ways .searchbar-example').allInnerTexts()
      check(examples.length === 3, `the card has three examples: ${examples.join(' | ')}`)
      // Read on this page without sending the visitor anywhere: an error says "RA first"; a
      // position that is read says so in the status line.
      for (const example of examples.slice(1)) {
        await page.fill('.searchbar-input', example)
        await page.keyboard.press('Enter')
        const said = await page
          .waitForFunction(() => document.querySelector('.searchbar [role=status]')?.textContent || document.querySelector('.searchbar [role=alert]')?.textContent, null, { timeout: 5000 })
          .then((h) => h.jsonValue())
          .catch(() => '')
        check(/^Coordinates read as RA 269\.446\d\d°, Dec \+4\.768\d\d°/.test(said), `typed "${example}": ${said || 'nothing was said'}`)
      }
      await page.fill('.searchbar-input', '+4.7682 269.4463')
      await page.keyboard.press('Enter')
      const refused = await page.locator('.searchbar [role=alert]').innerText()
      check(/Write RA first, then Dec/.test(refused) && !/then Dec\..*then Dec\./.test(refused), `Dec typed first is refused with the order, said once: ${refused.replace(/\s+/g, ' ')}`)
    }

    await page.goto(`${base}/?watchlist=1`, { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('#watch-place')
    const how = (await page.locator('#watch-how').innerText()).replace(/\s+/g, ' ')
    check(how.includes(ORDER) && /J2000/.test(how), `${width} px: the patch box has the instruction under it`)
    check((await page.locator('#watch-place').getAttribute('aria-describedby')) === 'watch-how', `${width} px: the patch box is described by it`)
    await page.locator('.region-picker').screenshot({ path: `${out}/patchbox-${width}.png` })
    await page.close()
  }
  await browser.close()
  console.log(failed ? `${failed} FAILED` : 'ALL PASS')
  process.exit(failed ? 1 : 0)
})()
