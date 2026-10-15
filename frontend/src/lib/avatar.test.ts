import { describe, expect, it } from 'vitest'
import { nameHue, nameInitials } from './avatar'

describe('the default avatar', () => {
  it('takes up to two initials of a name', () => {
    expect(nameInitials('Анна Петрова')).toBe('АП')
    expect(nameInitials('Гость')).toBe('Г')
    expect(nameInitials('  ')).toBe('?')
  })

  it('gives a name the same hue every time and two names different ones', () => {
    expect(nameHue('Анна Петрова')).toBe(nameHue('Анна Петрова'))
    expect(nameHue('Анна Петрова')).not.toBe(nameHue('Иван Смирнов'))
  })
})
