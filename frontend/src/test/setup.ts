// Setup of the component tests (the "dom" project, *.test.tsx in jsdom).
import '@testing-library/jest-dom/vitest'
import { toast } from '@heroui/react'
import { cleanup } from '@testing-library/react'
import { MotionGlobalConfig } from 'motion/react'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'
import { installBrowserFakes, resetBrowserFakes } from './browser'
import { server, settleRequests, unhandled } from './server'

// Every motion animation lands on its last frame at once: exits unmount
// without waiting, counters show their final number.
MotionGlobalConfig.skipAnimations = true

installBrowserFakes()

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))

afterEach(async () => {
  // Unmount first: the old screen must not start requests for the next test.
  cleanup()
  // Fake timers never outlive their test; the wait below needs real ones.
  vi.useRealTimers()
  await settleRequests()
  toast.clear()
  server.resetHandlers()
  resetBrowserFakes()
  localStorage.clear()
  sessionStorage.clear()
  if (unhandled.length > 0) {
    const missed = unhandled.splice(0)
    throw new Error(
      `Requests without a handler: ${missed.join(', ')}. ` +
        'Add a handler, or let the previous test wait until its screen has loaded.',
    )
  }
})

afterAll(() => server.close())
