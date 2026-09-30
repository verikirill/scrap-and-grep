// npm test
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { SAMPLE_PROPS } from '../src/sample.ts'
import { shortSchema } from '../src/schema.ts'
import { isWav, parseRange } from './assets.ts'
import { SerialQueue } from './queue.ts'

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
