import { describe, expect, it } from 'vitest'
import { periodChoice, scheduleDraft, scheduleLabel } from './schedule'

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

describe('periodChoice', () => {
  const choices = ['1', '3', '7', '14', '30']

  it('takes the period of the profile audience', () => {
    expect(periodChoice(1, choices)).toBe('1')
    expect(periodChoice(7, choices)).toBe('7')
  })

  it('falls back to a week for a period the panel does not offer', () => {
    expect(periodChoice(5, choices)).toBe('7')
    expect(periodChoice(undefined, choices)).toBe('7')
  })
})

describe('scheduleDraft', () => {
  it('starts the dialog from the schedule the audience suggests', () => {
    expect(scheduleDraft({ cadence: 'weekly', weekday: 0, time: '09:00' })).toEqual({
      cadence: 'weekly',
      weekday: 0,
      time: '09:00',
    })
  })

  it('keeps a weekday for the picker when the suggestion has none', () => {
    expect(scheduleDraft({ cadence: 'weekdays', weekday: null, time: '08:30' })).toEqual({
      cadence: 'weekdays',
      weekday: 0,
      time: '08:30',
    })
  })
})
