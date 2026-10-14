// Indicators of compromise as an article prints them: defanged, so that a
// paste into a chat opens nothing.

/** "evil[.]example" as a machine reads it, to tell its kind. */
function refang(value: string): string {
  return value
    .replace(/\[\.\]|\(\.\)/g, '.')
    .replace('[:]', ':')
    .replace(/^hxxp/i, 'http')
}

/** What an indicator is, in the words of a defender's checklist. */
export function indicatorKind(value: string): string {
  const plain = refang(value)
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(plain)) return 'IP'
  if (/^https?:\/\//i.test(plain)) return 'URL'
  if (/^[a-f0-9]{64}$/i.test(plain)) return 'SHA-256'
  if (/^[a-f0-9]{40}$/i.test(plain)) return 'SHA-1'
  if (/^[a-f0-9]{32}$/i.test(plain)) return 'MD5'
  return 'Домен'
}
