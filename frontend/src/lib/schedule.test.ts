import { describe, expect, it } from 'vitest'
import { scheduleLabel } from './schedule'

describe('scheduleLabel', () => {
  it('says when a schedule runs, with the day of a weekly one', () => {
    expect(scheduleLabel({ cadence: 'weekdays', weekday: null, time: '08:30' })).toBe(
      'по будням в 08:30',
    )
    expect(scheduleLabel({ cadence: 'weekly', weekday: 2, time: '20:00' })).toBe(
      'по средам в 20:00',
    )
    expect(scheduleLabel({ cadence: 'daily', weekday: null, time: '07:05' })).toBe(
      'каждый день в 07:05',
    )
  })
})
