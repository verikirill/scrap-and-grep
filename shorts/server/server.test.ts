// npm test
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { SAMPLE_PROPS } from '../src/sample.ts'
import { shortSchema } from '../src/schema.ts'
import { isWav, parseRange } from './assets.ts'
import { SerialQueue } from './queue.ts'
import { factShape, fitFontSize, formatCount, severityColor } from '../src/visuals.ts'
import { MAX_QR_SIZE, MIN_MODULE_PX, makeQr } from '../src/qr.ts'

describe('range requests for the narration', () => {
  it('serves the ranges the browser asks for', () => {
    assert.deepEqual(parseRange('bytes=0-99', 1000), [0, 99])
    assert.deepEqual(parseRange('bytes=900-', 1000), [900, 999])
    assert.deepEqual(parseRange('bytes=-100', 1000), [900, 999])
    // A range past the end is cut to the file.
    assert.deepEqual(parseRange('bytes=500-5000', 1000), [500, 999])
  })

  it('refuses what it cannot serve', () => {
    assert.equal(parseRange('bytes=2000-', 1000), null)
    assert.equal(parseRange('bytes=0-10,20-30', 1000), null)
    assert.equal(parseRange('items=0-1', 1000), null)
    assert.equal(parseRange('bytes=-', 1000), null)
    assert.equal(parseRange('bytes=-0', 1000), null)
    assert.equal(parseRange('bytes=0-', 0), null)
  })

  it('takes only WAV files', () => {
    const header = Buffer.alloc(64)
    header.write('RIFF', 0, 'latin1')
    header.write('WAVE', 8, 'latin1')
    assert.equal(isWav(header), true)
    assert.equal(isWav(Buffer.from('ID3 not a wave, however long it is........................')), false)
  })
})

describe('render queue', () => {
  it('runs jobs one after another, even after a failure', async () => {
    const queue = new SerialQueue(4)
    const order: string[] = []
    const slow = queue.run(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20))
      order.push('first')
      throw new Error('broken render')
    })
    const fast = queue.run(async () => {
      order.push('second')
      return 2
    })
    await assert.rejects(slow, /broken render/)
    assert.equal(await fast, 2)
    assert.deepEqual(order, ['first', 'second'])
  })

  it('holds a place for each request and gives it back once', () => {
    const queue = new SerialQueue(2)
    const first = queue.enter()
    const second = queue.enter()
    assert.ok(first && second)
    assert.equal(queue.enter(), null)
    // A client that leaves and a request that ends both give the place back.
    first()
    first()
    assert.equal(queue.size, 1)
    assert.notEqual(queue.enter(), null)
  })
})

describe('props schema', () => {
  it('accepts the sample the studio shows', () => {
    assert.equal(shortSchema.safeParse(SAMPLE_PROPS).success, true)
  })

  it('refuses a timeline that runs backwards', () => {
    const [first, ...rest] = SAMPLE_PROPS.beats
    const backwards = { ...SAMPLE_PROPS, beats: [{ ...first, endMs: first.startMs }, ...rest] }
    const late = { ...SAMPLE_PROPS, outroStartMs: SAMPLE_PROPS.durationMs + 1 }
    const [one, two, ...others] = SAMPLE_PROPS.beats
    const overlapping = { ...SAMPLE_PROPS, beats: [one, { ...two, startMs: one.endMs - 500 }, ...others] }
    const early = { ...SAMPLE_PROPS, beats: [{ ...one, startMs: SAMPLE_PROPS.hookEndMs - 1 }, two, ...others] }
    for (const props of [backwards, late, overlapping, early]) {
      assert.equal(shortSchema.safeParse(props).success, false)
    }
  })

  it('refuses text that would not fit the frame', () => {
    const long = { ...SAMPLE_PROPS, hook: 'слово '.repeat(40) }
    assert.equal(shortSchema.safeParse(long).success, false)
  })
})

describe('pictures of facts', () => {
  it('reads the shape of a fact', () => {
    assert.deepEqual(factShape('CVSS 9.8'), { kind: 'cvss', score: 9.8 })
    assert.deepEqual(factShape('27,7%'), { kind: 'percent', value: 27.7, label: '27,7%' })
    assert.deepEqual(factShape('48 часов'), { kind: 'number', value: 48, decimals: 0, suffix: 'часов' })
    assert.deepEqual(factShape('1,5 млрд рублей'), { kind: 'number', value: 1.5, decimals: 1, suffix: 'млрд рублей' })
    assert.deepEqual(factShape('12 000 записей'), { kind: 'number', value: 12000, decimals: 0, suffix: 'записей' })
    assert.deepEqual(factShape('CVE-2026-71379'), { kind: 'text', text: 'CVE-2026-71379' })
    // Not a score (CVSS stops at 10): shown as it is, as text.
    assert.equal(factShape('CVSS 12').kind, 'text')
  })

  it('does not count up what is not a count', () => {
    const notCounts = [
      '0-day', '5G', '10:30', 'версия 7.6.3', '30.09.2026', '7.6.3 и выше', '2026 год',
      '3 000', '12 10 раз', '30 сентября', '9007199254740993 записей',
    ]
    for (const fact of notCounts) {
      assert.equal(factShape(fact).kind, 'text', fact)
    }
  })

  it('counts millions and billions in their own words', () => {
    assert.deepEqual(factShape('1 500 000 000 рублей'), { kind: 'number', value: 1.5, decimals: 1, suffix: 'млрд рублей' })
    assert.deepEqual(factShape('12 345 678 записей'), { kind: 'number', value: 12.35, decimals: 2, suffix: 'млн записей' })
    assert.deepEqual(factShape('2 000 000 устройств'), { kind: 'number', value: 2, decimals: 0, suffix: 'млн устройств' })
  })

  it('prints a count the Russian way and fits it into the card', () => {
    assert.equal(formatCount(1.5, 1), '1,5')
    assert.equal(formatCount(9999, 0), '9999')
    assert.equal(formatCount(250000, 0), '250\u202f000')
    // Grouped by the digits shown, not by the value before rounding.
    assert.equal(formatCount(9999.6, 0), '10\u202f000')
    // The widest count a card can get still fits its 250 px at the size chosen.
    const widest = formatCount(999999.99, 2)
    assert.ok(fitFontSize(widest, 250, 88) * 0.7 * widest.length <= 250)
    assert.equal(fitFontSize('48', 250, 88), 88)
  })

  it('colours a CVSS score by the bands of the standard', () => {
    assert.equal(severityColor(9.8), severityColor(9))
    assert.notEqual(severityColor(8.9), severityColor(9))
    assert.notEqual(severityColor(3.9), severityColor(4))
  })
})

describe('source address on a card', () => {
  it('takes only web pages', () => {
    const [first, ...rest] = SAMPLE_PROPS.beats
    for (const url of ['javascript:alert(1)', 'file:///etc/passwd', 'https://exa mple.org']) {
      const props = { ...SAMPLE_PROPS, beats: [{ ...first, url }, ...rest] }
      assert.equal(shortSchema.safeParse(props).success, false, url)
    }
    const none = { ...SAMPLE_PROPS, beats: [{ ...first, url: null }, ...rest] }
    assert.equal(shortSchema.safeParse(none).success, true)
  })

  it('draws the QR code in whole pixels a module, or not at all', () => {
    const short = makeQr('https://example.org/1')
    const long = makeQr(`https://example.org/${'a'.repeat(180)}`)
    assert.ok(short && long)
    for (const qr of [short, long]) {
      assert.equal(qr.size, qr.px * qr.modules)
      assert.ok(qr.px >= MIN_MODULE_PX && qr.size <= MAX_QR_SIZE)
      // The quiet zone the standard asks for: four modules.
      assert.equal(qr.padding, 4 * qr.px)
    }
    // A denser code would have modules too small for a camera.
    assert.equal(makeQr(`https://example.org/${'a'.repeat(390)}`), null)
    // More than a QR code holds is no code, not a crash.
    assert.equal(makeQr('a'.repeat(5000)), null)
  })
})
