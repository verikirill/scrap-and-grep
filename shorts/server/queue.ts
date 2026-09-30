/**
 * Runs jobs one at a time. A render already takes every core through the
 * browser tabs Remotion opens, so two at once only make both slower.
 *
 * A request takes its place in line with `enter()` before anything is read
 * from it, so the limit holds however many requests arrive at once, and gives
 * it back with the returned function as soon as it is done or its client has
 * left. A job whose client left still passes through the line, but returns
 * at once when its turn comes.
 */
export class SerialQueue {
  private tail: Promise<unknown> = Promise.resolve()
  private taken = 0
  private readonly limit: number

  constructor(limit: number) {
    this.limit = limit
  }

  /** Places taken: requests waiting or running. */
  get size(): number {
    return this.taken
  }

  get isFull(): boolean {
    return this.taken >= this.limit
  }

  /** Take a place in line, or null when the line is full. The returned
   * function gives the place back; calling it twice is harmless. */
  enter(): (() => void) | null {
    if (this.isFull) {
      return null
    }
    this.taken += 1
    let isLeft = false
    return () => {
      if (!isLeft) {
        isLeft = true
        this.taken -= 1
      }
    }
  }

  /** Run the job after every job queued before it, whatever their outcome. */
  run<T>(job: () => Promise<T>): Promise<T> {
    const result = this.tail.then(job)
    this.tail = result.catch(() => undefined)
    return result
  }
}
