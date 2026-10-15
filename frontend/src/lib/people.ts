import type { PersonInput } from './company'

export interface PersonLine extends PersonInput {
  /** The line as it was pasted, for the preview. */
  line: string
  /** Why the line cannot be sent; null when it is fine. */
  problem: string | null
}

const EMAIL = /[^\s@<>,;|]+@[^\s@<>,;|]+\.[^\s@<>,;|]+/
const SEPARATORS = /[\t;,|]+/
export const MAX_PEOPLE = 100

/**
 * People from a pasted list, one per line, as a table or a mail client gives
 * them: «Анна Смирнова, anna@company.ru, инженер SOC», columns copied from a
 * spreadsheet, or «Анна Смирнова <anna@company.ru>». The address is found
 * wherever it stands; before it is the name, the rest is the position.
 */
export function parsePeople(text: string): PersonLine[] {
  const seen = new Set<string>()
  return text
    .split(/\r?\n/)
    .map((raw) => raw.trim())
    .filter(Boolean)
    .map((line) => {
      const found = EMAIL.exec(line)
      if (!found) {
        return { line, name: line, email: '', job_title: '', problem: 'Нет почты' }
      }
      const email = found[0].toLowerCase()
      const parts = (text: string) =>
        text
          .replace(/[<>]/g, ' ')
          .split(SEPARATORS)
          .map((part) => part.trim())
          .filter(Boolean)
      const before = parts(line.slice(0, found.index))
      const after = parts(line.slice(found.index + found[0].length))
      // Nothing before the address: the name is the first column after it.
      const name = before[0] ?? after.shift() ?? ''
      const job_title = [...before.slice(1), ...after].join(', ')
      const problem = seen.has(email) ? 'Почта повторяется' : null
      seen.add(email)
      return { line, name, email, job_title, problem }
    })
}
