import { describe, expect, it } from 'vitest'
import { parsePeople } from './people'

describe('parsePeople', () => {
  it('reads a name, an address and a position however the list was typed', () => {
    const rows = parsePeople(
      [
        'Анна Смирнова, Anna@Energo.ru, ведущий инженер SOC',
        'Олег Петров\toleg@energo.ru\tначальник отдела',
        'Вера Ким <vera@energo.ru>',
        'ira@energo.ru; Ирина; аналитик',
        '',
      ].join('\n'),
    )

    expect(rows.map(({ name, email, job_title }) => [name, email, job_title])).toEqual([
      ['Анна Смирнова', 'anna@energo.ru', 'ведущий инженер SOC'],
      ['Олег Петров', 'oleg@energo.ru', 'начальник отдела'],
      ['Вера Ким', 'vera@energo.ru', ''],
      ['Ирина', 'ira@energo.ru', 'аналитик'],
    ])
    expect(rows.every((row) => row.problem === null)).toBe(true)
  })

  it('marks a line without an address and a repeated address', () => {
    const rows = parsePeople('Пётр Иванов\nanna@energo.ru\nАнна, ANNA@energo.ru')

    expect(rows.map((row) => row.problem)).toEqual(['Нет почты', null, 'Почта повторяется'])
    expect(rows[0].line).toBe('Пётр Иванов')
  })
})
