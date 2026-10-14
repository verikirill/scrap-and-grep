// What comes with a digest besides its entries: the comparison of two issues,
// an answer about an issue, the spoken brief and the short video with their
// voices, and the progress events of a build.
import type {
  AskAnswer,
  AskCitation,
  Briefing,
  BriefingState,
  Comparison,
  InterestChange,
  ProgressEvent,
  ScoreChange,
  Video,
  VoiceOption,
} from '../../lib/api'
import { makeItem } from './digests'

/** The voices of the TTS service (tts/voices/voices.json); the first is the default. */
const VOICES: VoiceOption[] = [
  { id: 'anchor', title: 'Ведущий', default: true },
  { id: 'presenter', title: 'Ведущая', default: false },
  { id: 'blogger', title: 'Энергично', default: false },
  { id: 'analyst', title: 'Спокойно', default: false },
]

export function makeVoiceOption(overrides: Partial<VoiceOption> = {}): VoiceOption {
  return { ...VOICES[0], ...overrides }
}

/** The first `count` voices of the service, at most four. */
export function makeVoiceOptions(
  count = VOICES.length,
  overrides: Partial<VoiceOption> = {},
): VoiceOption[] {
  return VOICES.slice(0, count).map((voice) => ({ ...voice, ...overrides }))
}

export function makeInterestChange(overrides: Partial<InterestChange> = {}): InterestChange {
  return { id: 'interest-2', title: 'Атаки на энергетику', change: 'added', ...overrides }
}

/** An entry in both issues; its score in the newer one is base_score + delta. */
export function makeScoreChange(overrides: Partial<ScoreChange> = {}): ScoreChange {
  return { item: makeItem(), base_score: 0.74, delta: 0.07, ...overrides }
}

/** digest-2 against digest-1: one entry came, one left, one stayed and rose. */
export function makeComparison(overrides: Partial<Comparison> = {}): Comparison {
  return {
    base_id: 'digest-1',
    other_id: 'digest-2',
    added: [makeItem()],
    removed: [makeItem()],
    kept: [makeScoreChange()],
    interest_changes: [makeInterestChange()],
    settings_changed: ['min_score'],
    ...overrides,
  }
}

export function makeAskCitation(overrides: Partial<AskCitation> = {}): AskCitation {
  return {
    number: 1,
    headline: 'Уязвимость SIMATIC S7-1500 используется в атаках',
    url: 'https://www.securitylab.ru/news/562811.php',
    ...overrides,
  }
}

/** An answer found in the issue; "[1]" and "[2]" point at its entries. */
export function makeAskAnswer(overrides: Partial<AskAnswer> = {}): AskAnswer {
  return {
    answer:
      'Да, две записи. Уязвимость контроллеров SIMATIC S7-1500 уже используется в атаках [1], а подрядчикам сетевых компаний приходят фишинговые письма от имени Минэнерго [2].',
    citations: [
      makeAskCitation(),
      makeAskCitation({
        number: 2,
        headline: 'Фишинг от имени Минэнерго против подрядчиков сетевых компаний',
        url: 'https://ics-cert.kaspersky.ru/publications/minenergo-phishing-2026/',
      }),
    ],
    is_in_digest: true,
    ...overrides,
  }
}

/** A finished short video of digest-1, voiced by the default voice. */
export function makeVideo(overrides: Partial<Video> = {}): Video {
  return {
    status: 'done',
    stage: null,
    progress: 1,
    error: null,
    voice: 'qwen3-tts:anchor',
    requested_voice: 'anchor',
    by_model: true,
    duration_ms: 58_400,
    size_bytes: 6_815_744,
    created_at: '2026-10-14T09:05:00Z',
    finished_at: '2026-10-14T09:07:30Z',
    url: '/api/v1/digests/digest-1/short.mp4?v=1791968850',
    ...overrides,
  }
}

/** A finished spoken brief of a management digest, line by line as it is said. */
export function makeBriefing(overrides: Partial<Briefing> = {}): Briefing {
  return {
    status: 'done',
    progress: 1,
    error: null,
    voice: 'qwen3-tts:presenter',
    requested_voice: 'presenter',
    lines: [
      'Добрый день. За сутки три события, важные для энергетики.',
      'Главное: уязвимость контроллеров SIMATIC S7-1500 уже используется в атаках. Прошивку стоит обновить в ближайшее окно обслуживания.',
      'Минэнерго утвердило требования к защите объектов КИИ: до марта 2027 года защиту АСУ ТП переводят на отечественные средства.',
      'Подрядчикам сетевых компаний приходят фишинговые письма от имени министерства. Предупредите сотрудников.',
    ],
    duration_ms: 112_000,
    size_bytes: 3_584_044,
    created_at: '2026-10-14T09:10:00Z',
    finished_at: '2026-10-14T09:12:00Z',
    url: '/api/v1/digests/digest-1/briefing.wav?v=1791969120',
    ...overrides,
  }
}

export function makeBriefingState(overrides: Partial<BriefingState> = {}): BriefingState {
  return { available: true, voices: makeVoiceOptions(), briefing: makeBriefing(), ...overrides }
}

/** An event of a build's stream: grading the candidates, 16 of 40 done. */
export function makeProgressEvent(overrides: Partial<ProgressEvent> = {}): ProgressEvent {
  return {
    status: 'running',
    stage: 'grade',
    progress: 0.4,
    done: 16,
    total: 40,
    error: null,
    ...overrides,
  }
}
