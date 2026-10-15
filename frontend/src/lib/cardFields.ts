/**
 * Rows of the attack and vulnerability cards a reader may hide, as the
 * backend keys them (radar.domain.CardFieldKey, labels in radar.cards).
 * Hiding is presentation alone: the card is still filled and checked.
 */
export const CARD_FIELD_GROUPS = [
  {
    kind: 'attack',
    title: 'Атаки',
    fields: [
      { key: 'attack.victim_country', label: 'Страна жертвы' },
      { key: 'attack.group', label: 'Группировка' },
      { key: 'attack.date', label: 'Дата атаки' },
      { key: 'attack.sectors', label: 'Отрасли и компании' },
      { key: 'attack.vector', label: 'Вектор атаки' },
      { key: 'attack.initial_access', label: 'Первоначальный доступ' },
      { key: 'attack.affected', label: 'Затронутые продукты' },
      { key: 'attack.tools', label: 'Инструменты' },
      { key: 'attack.vulnerabilities', label: 'Уязвимости' },
      { key: 'attack.techniques', label: 'Техники ATT&CK' },
      { key: 'attack.indicators', label: 'Индикаторы компрометации' },
      { key: 'attack.references', label: 'Сверено по базам' },
    ],
  },
  {
    kind: 'vulnerability',
    title: 'Уязвимости',
    fields: [
      { key: 'vulnerability.name', label: 'Уязвимость' },
      { key: 'vulnerability.affected', label: 'Затронуто' },
      { key: 'vulnerability.fix', label: 'Обновление' },
      { key: 'vulnerability.workaround', label: 'Временные меры' },
      { key: 'vulnerability.exploit', label: 'Эксплойт' },
      { key: 'vulnerability.ids', label: 'Идентификаторы' },
      { key: 'vulnerability.cvss', label: 'CVSS' },
      { key: 'vulnerability.cvss_words', label: 'Доступ и права по CVSS' },
      { key: 'vulnerability.cwe', label: 'CWE' },
      { key: 'vulnerability.impact', label: 'Последствия' },
      { key: 'vulnerability.equipment', label: 'Оборудование' },
      { key: 'vulnerability.protocols', label: 'Протоколы' },
      { key: 'vulnerability.references', label: 'Сверено по базам' },
    ],
  },
] as const

export type CardFieldKey = (typeof CARD_FIELD_GROUPS)[number]['fields'][number]['key']

/** The hidden rows with one more hidden or shown again, in the catalogue's order. */
export function withHidden(
  hidden: readonly CardFieldKey[],
  key: CardFieldKey,
  isHidden: boolean,
): CardFieldKey[] {
  const next = new Set(hidden)
  if (isHidden) next.add(key)
  else next.delete(key)
  return CARD_FIELD_GROUPS.flatMap((group) => group.fields.map((field) => field.key)).filter(
    (item) => next.has(item),
  )
}
