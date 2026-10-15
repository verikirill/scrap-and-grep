// A specialist's digest entries as data: a vulnerability with what the reference
// bases say of it, an attack with its indicators, and the extras of an issue
// (the shift's checklist, news of earlier vulnerabilities, counts by tag and
// the handwork the issue spares).
import type {
  AttackData,
  DigestItem,
  Duplicate,
  ManualWork,
  PlanEntry,
  TagCount,
  VulnerabilityChange,
  VulnerabilityData,
  VulnerabilityReference,
} from '../../lib/api'
import { makeItem } from './digests'

const MALWARE_SHA256 = '4f6c2a91d8b37e05c9a1f4e62b8d0c73a5e9f1b2d4c6a8e0f3b5d7c9a1e2f4b6'

export function makeVulnerability(overrides: Partial<VulnerabilityData> = {}): VulnerabilityData {
  return {
    ids: ['CVE-2026-31842', 'BDU:2026-04187'],
    name: 'Обход аутентификации в веб-сервере SIMATIC S7-1500',
    cvss_score: '9.8',
    exploit: 'in_the_wild',
    ...overrides,
  }
}

/** CVE-2026-31842 as CISA KEV, the BDU, NVD, EPSS and Exploit-DB know it; dates as YYYY-MM-DD. */
export function makeReference(
  overrides: Partial<VulnerabilityReference> = {},
): VulnerabilityReference {
  return {
    id: 'CVE-2026-31842',
    kev_added: '2026-10-10',
    kev_due: '2026-10-31',
    kev_ransomware: false,
    bdu_id: 'BDU:2026-04187',
    bdu_cvss: '9.8',
    bdu_in_attacks: true,
    nvd_cvss: '9.8',
    nvd_exploitation: 'active',
    nvd_published: '2026-10-08',
    exploit_published: '2026-10-11',
    epss: 0.62,
    exploits: ['EDB-52417'],
    ...overrides,
  }
}

/** Indicators come defanged, technique names as ATT&CK gives them. */
export function makeAttack(overrides: Partial<AttackData> = {}): AttackData {
  return {
    indicators: ['185.244.25[.]17', 'minenergo-docs[.]ru', MALWARE_SHA256],
    techniques: [
      { id: 'T1566.001', name: 'Spearphishing Attachment' },
      { id: 'T1133', name: 'External Remote Services' },
    ],
    vulnerabilities: [],
    ...overrides,
  }
}

export function makeDuplicate(overrides: Partial<Duplicate> = {}): Duplicate {
  return {
    title: 'Siemens закрыла уязвимость в контроллерах S7-1500',
    url: 'https://www.anti-malware.ru/news/2026-10-14-111332/46012',
    source_name: 'Anti-Malware.ru',
    ...overrides,
  }
}

/** A high-priority vulnerability entry with its card in the dataset's order. */
export function makeVulnerabilityItem(overrides: Partial<DigestItem> = {}): DigestItem {
  return makeItem({
    url: 'https://www.securitylab.ru/news/562811.php',
    title: 'Уязвимость в контроллерах SIMATIC S7-1500 позволяет удалённо остановить ПЛК',
    headline: 'Уязвимость SIMATIC S7-1500 используется в атаках',
    summary:
      'Ошибка в веб-сервере контроллера даёт без пароля перезагрузить ПЛК и остановить технологический процесс. Исправление вошло в прошивку V3.1.5.',
    kind: 'vulnerability',
    priority: 'high',
    priority_reason: 'эксплойт: используется в атаках',
    fields: [
      {
        key: 'vulnerability.name',
        label: 'Уязвимость',
        value: 'Обход аутентификации в веб-сервере SIMATIC S7-1500',
      },
      {
        key: 'vulnerability.affected',
        label: 'Затронуто',
        value: 'SIMATIC S7-1500 CPU с прошивкой до V3.1.5',
      },
      { key: 'vulnerability.fix', label: 'Обновление', value: 'Прошивка V3.1.5' },
      {
        key: 'vulnerability.workaround',
        label: 'Временные меры',
        value: 'Закрыть доступ к порту 443 из корпоративной сети',
      },
      { key: 'vulnerability.exploit', label: 'Эксплойт', value: 'используется в атаках' },
      {
        key: 'vulnerability.ids',
        label: 'Идентификаторы',
        value: 'CVE-2026-31842, BDU:2026-04187',
      },
      {
        key: 'vulnerability.cvss',
        label: 'CVSS',
        value: '9.8 (CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H)',
      },
      { key: 'vulnerability.cvss_words', label: 'Доступ', value: 'по сети' },
      { key: 'vulnerability.cvss_words', label: 'Сложность', value: 'низкая' },
      { key: 'vulnerability.cvss_words', label: 'Права', value: 'не нужны' },
      { key: 'vulnerability.cvss_words', label: 'Действия пользователя', value: 'не нужны' },
      { key: 'vulnerability.cwe', label: 'CWE', value: 'CWE-287' },
      {
        key: 'vulnerability.impact',
        label: 'Последствия',
        value: 'Остановка контроллера и технологического процесса',
      },
      {
        key: 'vulnerability.equipment',
        label: 'Оборудование',
        value: 'Программируемые логические контроллеры',
      },
      { key: 'vulnerability.protocols', label: 'Протоколы', value: 'HTTPS, S7comm' },
    ],
    vulnerability: makeVulnerability(),
    references: [makeReference()],
    ...overrides,
  })
}

/** A high-priority attack on the Russian energy sector with its card. */
export function makeAttackItem(overrides: Partial<DigestItem> = {}): DigestItem {
  return makeItem({
    url: 'https://ics-cert.kaspersky.ru/publications/minenergo-phishing-2026/',
    title: 'Фишинг от имени Минэнерго нацелен на подрядчиков сетевых компаний',
    headline: 'Фишинг от имени Минэнерго против подрядчиков сетевых компаний',
    source_name: 'Kaspersky ICS CERT',
    source_category: 'ics',
    summary:
      'Письма о «новых требованиях к отчётности» несут загрузчик бэкдора. Злоумышленники ищут учётные данные для удалённого доступа к подстанциям.',
    kind: 'attack',
    priority: 'high',
    priority_reason: 'РФ, энергетика или промышленность',
    fields: [
      { key: 'attack.victim_country', label: 'Страна жертвы', value: 'Россия' },
      { key: 'attack.group', label: 'Группировка', value: 'нет данных' },
      { key: 'attack.date', label: 'Дата атаки', value: 'октябрь 2026' },
      {
        key: 'attack.sectors',
        label: 'Отрасли и компании',
        value: 'Подрядчики электросетевых компаний',
      },
      {
        key: 'attack.vector',
        label: 'Вектор атаки',
        value: 'Фишинговые письма от имени Минэнерго',
      },
      {
        key: 'attack.initial_access',
        label: 'Первоначальный доступ',
        value: 'Вложение с загрузчиком бэкдора',
      },
      { key: 'attack.affected', label: 'Затронутые продукты', value: 'Microsoft Windows' },
      { key: 'attack.tools', label: 'Инструменты', value: 'нет данных' },
      { key: 'attack.vulnerabilities', label: 'Уязвимости', value: 'нет данных' },
      {
        key: 'attack.techniques',
        label: 'Техники ATT&CK',
        value: 'T1566.001 Spearphishing Attachment; T1133 External Remote Services',
      },
      {
        key: 'attack.indicators',
        label: 'Индикаторы компрометации',
        value: `185.244.25[.]17, minenergo-docs[.]ru, ${MALWARE_SHA256}`,
      },
    ],
    attack: makeAttack(),
    ...overrides,
  })
}

/** A line of the shift's checklist for a high-priority vulnerability. */
export function makePlanEntry(overrides: Partial<PlanEntry> = {}): PlanEntry {
  return {
    headline: 'Уязвимость SIMATIC S7-1500 используется в атаках',
    url: 'https://www.securitylab.ru/news/562811.php',
    kind: 'vulnerability',
    steps: [
      'Обновление: прошивка V3.1.5',
      'Временные меры: закрыть доступ к порту 443 из корпоративной сети',
    ],
    facts: ['в каталоге CISA KEV с 10.10.2026, устранить до 31.10.2026', 'EPSS 62%', 'CVSS 9.8'],
    ...overrides,
  }
}

/** What became known about a vulnerability an earlier issue had. */
export function makeVulnerabilityChange(
  overrides: Partial<VulnerabilityChange> = {},
): VulnerabilityChange {
  return {
    id: 'CVE-2026-28977',
    headline: 'Обход аутентификации в VPN-шлюзах удалённого доступа',
    url: 'https://www.securitylab.ru/news/561904.php',
    since: '2026-10-09',
    what: [
      'попала в каталог CISA KEV 13.10.2026',
      'эксплойт: было «нет данных», стало «используется в атаках»',
    ],
    ...overrides,
  }
}

/** Entries of a management issue under one tag, beside the previous issue's. */
export function makeTagCount(overrides: Partial<TagCount> = {}): TagCount {
  return { tag: 'energy', label: 'Энергетика', count: 4, before: 2, ...overrides }
}

/** What makeSummary()'s issue spares: 300 headlines at 5 s and 12 entries at 3 min,
 * done by the build in 48 s. */
export function makeManualWork(overrides: Partial<ManualWork> = {}): ManualWork {
  return {
    headlines: 300,
    entries: 12,
    minutes: 61,
    seconds: 48,
    seconds_per_headline: 1.3,
    minutes_per_entry: 4.6,
    ...overrides,
  }
}
