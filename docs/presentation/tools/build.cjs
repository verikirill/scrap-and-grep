// Builds the deck from slides.html: a PDF and what the PPTX builder needs.
//
//   node docs/presentation/tools/build.cjs docs/presentation/slides.html <workDir> [out.pdf]
//
// The frosted panels use backdrop-filter, which Chromium drops when it prints. So every slide is
// rendered as a picture first, with the text made transparent, and the PDF puts the live text
// over that picture: it stays sharp, selectable and searchable.
//
// For the PPTX it writes <workDir>/deck.json with every text block (box, paddings, runs with
// their font, size and colour), a background per slide without text and pictures
// (<workDir>/bg/sNN.jpg), and each picture alone on a transparent PNG (<workDir>/pic/*.png):
// device frames with their screens, the cat, the Telegram post. Pictures and text stay movable.
//
// playwright-core is taken from PLAYWRIGHT_CORE or from node_modules; the browser is Chrome
// or Edge, or CHROME_PATH.
const { chromium } = require(process.env.PLAYWRIGHT_CORE || 'playwright-core')
const fs = require('fs')
const path = require('path')
const { pathToFileURL } = require('url')

const [HTML, WORK, PDF] = process.argv.slice(2)
if (!HTML || !WORK) {
  console.error('usage: node build.cjs <slides.html> <workDir> [out.pdf]')
  process.exit(2)
}
const W = 1920
const H = 1080
const SCALE = 2
// What goes into the PPTX as a picture of its own. A callout is a picture under its own text:
// it lies over a device frame and must stay above it.
const PICTURES = '.device, .cat, img.pic, .foot .mark, .callout'
const SHADOW = 60

const MODES = `
.m-notext .slide *, .m-notext .slide *::before, .m-notext .slide *::after {
  color: transparent !important; -webkit-text-fill-color: transparent !important; text-shadow: none !important;
}
.m-notext .slide .device *, .m-notext .slide .device *::before, .m-notext .slide .device *::after {
  color: revert !important; -webkit-text-fill-color: revert !important;
}
.m-nopic .slide :is(${PICTURES}) { visibility: hidden !important; }
html.m-iso, html.m-iso body, .m-iso .slide { background: transparent !important; }
.m-iso .slide * { visibility: hidden !important; }
.m-iso .slide .pp-target, .m-iso .slide .pp-target * { visibility: visible !important; }
.m-text .slide { background-size: 100% 100% !important; }
.m-text .slide *, .m-text .slide *::before, .m-text .slide *::after {
  background: transparent !important; border-color: transparent !important; box-shadow: none !important;
  -webkit-backdrop-filter: none !important; backdrop-filter: none !important; outline: none !important;
}
.m-text .slide :is(img, svg, .bg), .m-text .slide *::before, .m-text .slide *::after { visibility: hidden !important; }
.m-text .slide .device, .m-text .slide .device * { visibility: hidden !important; }
`

function collect(pictureSelector) {
  const slide = document.querySelector('section.slide.pp-current')
  const base = slide.getBoundingClientRect()
  const rel = (r) => ({ x: r.left - base.left, y: r.top - base.top, w: r.width, h: r.height })
  const style = (e) => {
    const cs = getComputedStyle(e)
    return {
      color: cs.color, weight: Number(cs.fontWeight), italic: cs.fontStyle === 'italic',
      size: parseFloat(cs.fontSize), family: cs.fontFamily, transform: cs.textTransform,
      ls: cs.letterSpacing, ws: cs.whiteSpace, mono: /mono|consolas/i.test(cs.fontFamily),
      va: cs.verticalAlign,
    }
  }
  const isInline = (e) => getComputedStyle(e).display === 'inline'
  // Each run lists the offsets where a new line starts, as the browser laid the text out.
  const runs = (node, lh, state = { top: null }, out = []) => {
    for (const c of node.childNodes) {
      if (c.nodeType === 3) {
        const breaks = []
        for (let k = 0; k < c.data.length; k++) {
          if (/\s/.test(c.data[k])) continue
          const range = document.createRange()
          range.setStart(c, k)
          range.setEnd(c, k + 1)
          const rects = range.getClientRects()
          if (!rects.length) continue
          const t = rects[0].top
          if (state.top !== null && t > state.top + lh * 0.5) breaks.push(k)
          if (state.top === null || t > state.top + lh * 0.5) state.top = t
        }
        out.push({ text: c.data, style: style(c.parentElement), breaks })
      } else if (c.nodeType === 1 && c.tagName === 'BR') out.push({ br: true })
      else if (c.nodeType === 1 && isInline(c) && c.tagName !== 'svg' && c.tagName !== 'IMG') runs(c, lh, state, out)
    }
    return out
  }
  const hasOwnText = (e) => [...e.childNodes].some((c) =>
    (c.nodeType === 3 && c.data.trim() !== '') ||
    (c.nodeType === 1 && isInline(c) && c.tagName !== 'svg' && c.textContent.trim() !== ''))
  // The box of the text itself: a flex row or a block with other blocks inside is measured by
  // the range of its own text.
  const textRect = (e) => {
    const own = [...e.childNodes].filter((c) => c.nodeType === 3 || (c.nodeType === 1 && isInline(c) && c.tagName !== 'svg'))
    const r = document.createRange()
    r.setStartBefore(own[0])
    r.setEndAfter(own[own.length - 1])
    return r.getBoundingClientRect()
  }
  const texts = []
  for (const e of slide.querySelectorAll('*')) {
    if (e.closest('.device') || e.closest('.bg') || e.tagName === 'svg' || e.closest('svg')) continue
    const cs = getComputedStyle(e)
    if (cs.display === 'inline' || cs.display === 'none' || cs.visibility === 'hidden' || !hasOwnText(e)) continue
    const mixed = [...e.children].some((c) => !isInline(c)) || cs.display.includes('flex') || cs.display.includes('grid')
    const lh = cs.lineHeight === 'normal' ? parseFloat(cs.fontSize) * 1.2 : parseFloat(cs.lineHeight)
    let rect
    let pad
    if (mixed) {
      rect = rel(textRect(e))
      pad = [0, 0, 0, 0]
    } else {
      rect = rel(e.getBoundingClientRect())
      pad = [cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft].map(parseFloat)
      const bw = [cs.borderTopWidth, cs.borderRightWidth, cs.borderBottomWidth, cs.borderLeftWidth].map(parseFloat)
      pad = pad.map((p, i) => p + bw[i])
    }
    const own = runs(e, lh)
    texts.push({
      rect, pad, align: cs.textAlign, lineHeight: lh,
      lineCount: 1 + own.reduce((n, r) => n + (r.breaks ? r.breaks.length : 0), 0),
      nowrap: cs.whiteSpace === 'nowrap', runs: own, tag: e.tagName.toLowerCase(),
    })
  }
  const pictures = [...slide.querySelectorAll(pictureSelector)].map((e, k) => {
    const img = e.tagName === 'IMG' ? e : e.querySelector('img')
    const kind = ['device', 'cat', 'callout'].find((c) => e.classList.contains(c)) || 'image'
    // A screen with data-gif plays that GIF in the PPTX: its visible part on the screen,
    // with the crop of what the screen hides and the screen's corner radius.
    const g = e.querySelector('img[data-gif]')
    let gif = null
    if (g) {
      const box = g.getBoundingClientRect()
      const scr = g.closest('.screen').getBoundingClientRect()
      let c = { left: box.left, top: box.top, width: box.width, height: box.height }
      if (getComputedStyle(g).objectFit === 'contain') {
        const ar = g.naturalWidth / g.naturalHeight
        if (box.width / box.height > ar) c = { left: box.left + (box.width - box.height * ar) / 2, top: box.top, width: box.height * ar, height: box.height }
        else c = { left: box.left, top: box.top + (box.height - box.width / ar) / 2, width: box.width, height: box.width / ar }
      }
      const v = {
        left: Math.max(c.left, scr.left), top: Math.max(c.top, scr.top),
        right: Math.min(c.left + c.width, scr.right), bottom: Math.min(c.top + c.height, scr.bottom),
      }
      gif = {
        src: g.getAttribute('data-gif'),
        rect: rel({ left: v.left, top: v.top, width: v.right - v.left, height: v.bottom - v.top }),
        crop: {
          l: (v.left - c.left) / c.width, t: (v.top - c.top) / c.height,
          r: (c.left + c.width - v.right) / c.width, b: (c.top + c.height - v.bottom) / c.height,
        },
        radius: parseFloat(getComputedStyle(g.closest('.screen')).borderTopLeftRadius) || 0,
      }
    }
    return { k, rect: rel(e.getBoundingClientRect()), alt: img ? img.alt : e.textContent.trim(), kind, gif }
  })
  return { texts, pictures }
}

async function launch() {
  if (process.env.CHROME_PATH) return chromium.launch({ executablePath: process.env.CHROME_PATH })
  return chromium.launch({ channel: 'chrome' }).catch(() => chromium.launch({ channel: 'msedge' }))
}

async function main() {
  for (const dir of ['bg', 'full', 'pic']) fs.mkdirSync(path.join(WORK, dir), { recursive: true })
  const browser = await launch()
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: SCALE })
  await page.goto(pathToFileURL(path.resolve(HTML)).href, { waitUntil: 'load' })
  await page.addStyleTag({ content: MODES })
  await page.evaluate(() => document.fonts.ready)
  const count = await page.locator('section.slide').count()
  const deck = []
  const mode = (...m) => page.evaluate((m) => { document.documentElement.className = m.join(' ') }, m)
  for (let i = 0; i < count; i++) {
    const num = String(i + 1).padStart(2, '0')
    const section = page.locator('section.slide').nth(i)
    await page.evaluate((i) => document.querySelectorAll('section.slide').forEach((s, j) => s.classList.toggle('pp-current', j === i)), i)
    await section.scrollIntoViewIfNeeded()
    await mode()
    const data = await page.evaluate(collect, PICTURES)
    // The picture under the live text of the PDF, and the PPTX background without pictures.
    await mode('m-notext')
    await section.screenshot({ path: path.join(WORK, 'full', `s${num}.jpg`), type: 'jpeg', quality: 88 })
    await mode('m-notext', 'm-nopic')
    await section.screenshot({ path: path.join(WORK, 'bg', `s${num}.jpg`), type: 'jpeg', quality: 88 })
    // Each picture alone on a transparent background, with room for its shadow.
    const box = await section.boundingBox()
    for (const p of data.pictures) {
      await mode(...(p.kind === 'callout' ? ['m-iso', 'm-notext'] : ['m-iso']))
      await page.evaluate(({ i, k, sel }) => {
        const s = document.querySelectorAll('section.slide')[i]
        s.querySelectorAll('.pp-target').forEach((e) => e.classList.remove('pp-target'))
        s.querySelectorAll(sel)[k].classList.add('pp-target')
      }, { i, k: p.k, sel: PICTURES })
      const m = p.kind === 'device' || p.kind === 'callout' ? SHADOW : 0
      const x0 = Math.max(0, Math.floor(p.rect.x - m))
      const y0 = Math.max(0, Math.floor(p.rect.y - m))
      const x1 = Math.min(W, Math.ceil(p.rect.x + p.rect.w + m))
      const y1 = Math.min(H, Math.ceil(p.rect.y + p.rect.h + m))
      p.clip = { x: x0, y: y0, w: x1 - x0, h: y1 - y0 }
      p.file = `pic/s${num}-${String(p.k + 1).padStart(2, '0')}-${p.kind}.png`
      await page.screenshot({
        path: path.join(WORK, p.file), omitBackground: true,
        clip: { x: box.x + x0, y: box.y + y0, width: x1 - x0, height: y1 - y0 },
      })
    }
    for (const p of data.pictures) if (p.gif) p.gif.file = path.resolve(path.dirname(HTML), p.gif.src)
    deck.push({ ...data, bg: `bg/s${num}.jpg` })
  }
  fs.writeFileSync(path.join(WORK, 'deck.json'), JSON.stringify(deck, null, 1))

  if (PDF) {
    // Live text over the rendered slides.
    await mode('m-text')
    await page.evaluate((files) => {
      document.querySelectorAll('section.slide').forEach((s, i) => {
        s.style.backgroundImage = `url("${files[i]}")`
      })
    }, deck.map((_, i) => pathToFileURL(path.resolve(WORK, 'full', `s${String(i + 1).padStart(2, '0')}.jpg`)).href))
    await page.evaluate(() => Promise.all([...document.querySelectorAll('section.slide')].map((s) => {
      const img = new Image()
      img.src = getComputedStyle(s).backgroundImage.slice(5, -2)
      return img.decode()
    })))
    await page.emulateMedia({ media: 'print' })
    await page.pdf({ path: PDF, preferCSSPageSize: true, printBackground: true })
  }
  await browser.close()
  console.log(`${count} slides${PDF ? ` -> ${PDF}` : ''}`)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
