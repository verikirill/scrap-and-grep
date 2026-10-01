import type { ShortProps } from './types'

/**
 * Props for the studio and for the smoke render: a made-up week with the
 * shape the backend produces. Word timings are spread evenly here; the
 * backend takes them from the narration.
 */
function words(text: string, startMs: number, endMs: number) {
  const parts = text.split(/\s+/).filter(Boolean)
  const step = (endMs - startMs) / parts.length
  return parts.map((part, index) => ({
    text: part,
    startMs: Math.round(startMs + index * step),
    endMs: Math.round(startMs + (index + 1) * step),
  }))
}

const HOOK = 'Три новости ИБ для энергетики за неделю'
const LINES = [
  'Siemens закрыла критическую уязвимость в контроллерах SIMATIC.',
  'ФСТЭК обновила требования к значимым объектам КИИ.',
  'Шифровальщик остановил диспетчерскую европейской сетевой компании.',
]
const OUTRO = 'Полный дайджест со ссылками ждёт в Радаре'

export const SAMPLE_PROPS: ShortProps = {
  brand: 'Радар',
  period: '23-30 сентября',
  audience: 'ИБ АСУ ТП',
  hook: HOOK,
  hookEndMs: 3000,
  beats: [
    {
      kicker: 'Уязвимость',
      title: 'Критическая дыра в контроллерах Siemens SIMATIC',
      fact: 'CVSS 9.8',
      visual: 'vulnerability',
      points: ['Удалённый останов ПЛК', 'Исправление уже вышло', 'Затронуты S7-1500'],
      source: 'SecurityWeek',
      url: 'https://example.org/news/siemens-simatic',
      date: '29 сентября',
      startMs: 3000,
      endMs: 8000,
    },
    {
      kicker: 'Регулятор',
      title: 'ФСТЭК обновила требования к объектам КИИ',
      fact: 'до 31 декабря',
      visual: 'regulation',
      points: ['Новая методика оценки угроз', 'Касается значимых объектов'],
      source: 'НКЦКИ',
      url: 'https://example.org/news/fstec-kii',
      date: '27 сентября',
      startMs: 8000,
      endMs: 13000,
    },
    {
      kicker: 'Инцидент',
      title: 'Шифровальщик остановил диспетчерскую',
      fact: '48 часов',
      visual: 'incident',
      points: ['Ручное управление сетью', 'Данные клиентов не утекли'],
      source: 'Industrial Cyber',
      url: 'https://example.org/news/ransomware-dispatch',
      date: '25 сентября',
      startMs: 13000,
      endMs: 18000,
    },
  ],
  outro: OUTRO,
  outroStartMs: 18000,
  words: [
    ...words(HOOK, 200, 2800),
    ...words(LINES[0], 3100, 7800),
    ...words(LINES[1], 8100, 12800),
    ...words(LINES[2], 13100, 17800),
    ...words(OUTRO, 18100, 20600),
  ],
  audioSrc: null,
  durationMs: 21000,
}
