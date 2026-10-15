---
profile: "Специалист по ИБ АСУ ТП"
profile_version: 1
audience: "specialist"
period_start: "2026-09-25"
period_end: "2026-10-02"
generated: "2026-10-15T06:03+03:00"
llm: "heuristic"
embedding: "ollama:embeddinggemma:300m"
sources: 14
publications: 1716
candidates: 60
entries: 20
manual_minutes: 129
---

# Дайджест для профиля «Специалист по ИБ АСУ ТП»

**Профиль:** Специалист по ИБ АСУ ТП (версия 1)  
**Период:** 25.09.2026 - 02.10.2026  
**Сформирован:** 15.10.2026 06:03 МСК

*Вместо ручной работы: ассистент просмотрел 1 716 публикаций и написал 20 записей за 1 с; вручную это около 2,1 ч по журналу аналитика ИБ: 1,3 с на публикацию и 4,6 мин на запись.*

## Содержание

- [1. Атаки](#1-атаки)
- [2. Уязвимости](#2-уязвимости)
- [3. Требования регуляторов по ИБ](#3-требования-регуляторов-по-иб)
- [4. Безопасность АСУ ТП и промышленных систем](#4-безопасность-асу-тп-и-промышленных-систем)

## Главное

- На KazHackStan я слушал выступление Дениса Ласкова про атаки на критическую инфраструктуру и зацепила меня одна история
- Schneider Electric, SECLAB expand OT cybersecurity collaboration for industrial infrastructure
- ФСТЭК разъяснила порядок и сроки представления результатов оценки защищённости информационных систем
- One Packet Can Crash OT Servers in Industrial Sectors

## План на смену

- [ ] [Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в Citrix NetScaler, связанной с развертыванием веб-оболочек и вредоносного ПО для туннелирования, получением root-доступа…](https://t.me/true_secator/8662)
  - Устранение по БДУ: обновление программного обеспечения
  - в каталоге CISA KEV с 27.09.2026, устранить до 30.09.2026; EPSS 1,3%; CVSS 9; эксплойт: используется в атаках
- [ ] [Schneider Electric, SECLAB expand OT cybersecurity collaboration for industrial infrastructure](https://industrialcyber.co/news/schneider-electric-seclab-expand-ot-cybersecurity-collaboration-for-industrial-infrastructure)
  - эксплойт: используется в атаках

## 1. Атаки

Высокий приоритет: 1. Порядок по правилу: атаки на ТЭК и промышленность РФ приоритетнее других отраслей РФ, зарубежные инциденты - в конце.

### [На KazHackStan я слушал выступление Дениса Ласкова про атаки на критическую инфраструктуру и зацепила меня одна история](https://t.me/alukatsky/15356)

*Пост Лукацкого · 02.10.2026 · Атака · приоритет: высокий (РФ, энергетика или промышленность) · релевантность 1.00 · интерес: Атаки на энергетику и критическую инфраструктуру*

Я про нее знал, но Денис показал ее немного с иной стороны (слушать с 1:11:11). Речь об инцидентах в системе водоснабжения США. Я видел сообщения об атаке то на один штат, то на другой, но Денис свел все это вместе и картинка стала немного иной. Я пошел немного покопаться в этой истории и она стала выглядеть более примечательной. Несмотря на то, что все говорят о начале атак в…

| Поле | Значение |
| --- | --- |
| Страна жертвы | нет данных |
| Группировка | нет данных |
| Дата атаки | нет данных |
| Отрасли и компании | нет данных |
| Вектор атаки | нет данных |
| Первоначальный доступ | нет данных |
| Затронутые продукты | нет данных |
| Инструменты | нет данных |
| Уязвимости | нет данных |
| Техники ATT&CK | нет данных |
| Индикаторы компрометации | нет данных |

**Почему важно:** Интерес «Атаки на энергетику и критическую инфраструктуру»: ключевые слова: критическая инфраструктура, КИИ.

## 2. Уязвимости

Высокий приоритет: 3; средний приоритет: 7. Порядок по правилу: уязвимости с известным эксплойтом показываются первыми.

### [Schneider Electric, SECLAB expand OT cybersecurity collaboration for industrial infrastructure](https://industrialcyber.co/news/schneider-electric-seclab-expand-ot-cybersecurity-collaboration-for-industrial-infrastructure)

*Industrial Cyber · касается нас: Schneider Electric · 29.09.2026 · Уязвимость · приоритет: высокий (эксплойт: используется в атаках) · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

Schneider Electric, a global energy technology leader, and SECLAB, a French provider of OT cybersecurity solutions, announced an... The post Schneider Electric, SECLAB expand OT cybersecurity collaboration for industrial infrastructure appeared first on Industrial Cyber .

| Поле | Значение |
| --- | --- |
| Уязвимость | нет данных |
| Затронуто | нет данных |
| Обновление | нет данных |
| Временные меры | нет данных |
| Эксплойт | используется в атаках |
| Идентификаторы | нет данных |
| CVSS | нет данных |
| CWE | нет данных |
| Последствия | нет данных |

**Почему важно:** Интерес «Безопасность АСУ ТП и промышленных систем»: ключевые слова: OT, Schneider Electric, PLC.

### [Две уязвимости в CODESYS позволяют вызвать отказ в обслуживании и исказить данные мониторинга](https://1275.ru/vulnerability/dve-uyazvimosti-v-codesys-pozvolyayut-vyzvat-otkaz-v-obsluzhivanii-i-iskazit-dannye-monitoringa_42653)

*1275.ru: уязвимости и индикаторы · касается нас: CODESYS · 02.10.2026 · Уязвимость · приоритет: средний (эксплойт: нет) · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

В средах разработки и исполнения CODESYS обнаружили две уязвимости. Одна даёт чужому шлюзу возможность исчерпать память клиентской программы, вторая искажает данные, когда к контроллеру одновременно обращаются несколько систем. Разработчик CODESYS GmbH исправляет обе в версиях 3.5.22.40 и 4.23.0.0. Вторая выйдет только в четвёртом квартале 2026 года, поэтому часть контроллеров…

| Поле | Значение |
| --- | --- |
| Уязвимость | нет данных |
| Затронуто | нет данных |
| Обновление | Для части версий исправление ещё не выпущено. |
| Временные меры | нет данных |
| Эксплойт | нет |
| Идентификаторы | CVE-2026-76992, CVE-2026-79625 |
| CVSS | нет данных |
| CWE | нет данных |
| Последствия | нет данных |
| Сверено по базам | CVE-2026-76992: EPSS 0,3%; CVE-2026-79625: EPSS 0,2% |

**Почему важно:** Интерес «Безопасность АСУ ТП и промышленных систем»: близость по содержанию.

### [ABB Protection and Control IED Manager PCM600](https://cisa.gov/news-events/ics-advisories/icsa-26-274-03)

*CISA ICS Advisories · касается нас: ABB PCM600 · 01.10.2026 · Уязвимость · приоритет: средний (эксплойт: нет данных) · релевантность 0.92 · интерес: Безопасность АСУ ТП и промышленных систем*

View CSAF Summary Successful exploitation of these vulnerabilities could allow an attacker to escalate privileges or overwrite files. The following versions of ABB Protection and Control IED Manager PCM600 are affected: Protection and Control IED Manager PCM600 \<=2.14 (CVE-2026-15952, CVE-2026-15953) CVSS Vendor Equipment Vulnerabilities v3 6.4 ABB ABB Protection and Control…

| Поле | Значение |
| --- | --- |
| Уязвимость | нет данных |
| Затронуто | нет данных |
| Обновление | нет данных |
| Временные меры | нет данных |
| Эксплойт | нет данных |
| Идентификаторы | CVE-2026-15952, CVE-2026-15953 |
| CVSS | 3.1 (CVSS:3.1/AV:L/AC:H/PR:H/UI:N/S:U/C:H/I:H/A:H) |
| Доступ | локально |
| Сложность | высокая |
| Права | высокие |
| Действия пользователя | не нужны |
| CWE | CWE-732 |
| Последствия | нет данных |
| Сверено по базам | CVE-2026-15952: EPSS 0,1%; CVE-2026-15953: EPSS 0,1% |

**Почему важно:** Интерес «Безопасность АСУ ТП и промышленных систем»: близость по содержанию.

### [Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в Citrix NetScaler, связанной с развертыванием веб-оболочек и вредоносного ПО для туннелирования, получением root-доступа…](https://t.me/true_secator/8662)

*SecAtor · 30.09.2026 · Уязвимость · приоритет: высокий (эксплойт: используется в атаках) · релевантность 0.87 · интерес: Уязвимости и обновления безопасности*

Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в Citrix NetScaler, связанной с развертыванием веб-оболочек и вредоносного ПО для туннелирования, получением root-доступа и кражей учетных данных. Атаки стартовали как минимум с начала сентября и, как полагают исследователи, затронули организации в Северной Америке и Европе из правительственного, финансовоого…

| Поле | Значение |
| --- | --- |
| Уязвимость | нет данных |
| Затронуто | нет данных |
| Обновление | нет данных |
| Временные меры | нет данных |
| Эксплойт | используется в атаках |
| Идентификаторы | CVE-2026-88772, CVE-2026-88771 |
| CVSS | нет данных |
| CWE | нет данных |
| Последствия | нет данных |
| Сверено по базам | CVE-2026-88772: CISA KEV с 27.09.2026, устранить до 30.09.2026; BDU:2026-15497, эксплойт существует в открытом доступе, используется в атаках; EPSS 1,3%; CVE-2026-88771: CISA KEV с 27.09.2026, устранить до 30.09.2026; BDU:2026-15496, эксплойт существует, используется в атаках; EPSS 1,1% |

**Почему важно:** Интерес «Уязвимости и обновления безопасности»: ключевые слова: уязвимость, CVE, 0-day, RCE.

Также об этом: [ZeroDay Alert](https://t.me/ZerodayAlert/854), [BleepingComputer](https://bleepingcomputer.com/news/security/hackers-exploit-citrix-netscaler-zero-day-to-deploy-web-shells), [Google Cloud: Threat Intelligence](https://cloud.google.com/blog/topics/threat-intelligence/defending-against-active-exploitation-of-citrix-netscaler-adc-and-gateway-appliances), [The Register: Security](https://theregister.com/security/2026/09/29/custom-malware-used-in-citrix-0-day-attacks-targeting-govt-banks-professional-services/5299867)

### [Сентябрьский дайджест трендовых уязвимостей](https://ptsecurity.com/research/analytics/trending-vulnerability-digest-september-2026/)

*Positive Technologies: новости · 25.09.2026 · Уязвимость · приоритет: высокий (эксплойт: используется в атаках) · релевантность 0.87 · интерес: Уязвимости и обновления безопасности*

Сентябрьский дайджест трендовых уязвимостей - исследование Positive Technologies. Ключевые выводы, данные и рекомендации экспертов в области кибербезопасности.

| Поле | Значение |
| --- | --- |
| Уязвимость | нет данных |
| Затронуто | нет данных |
| Обновление | нет данных |
| Временные меры | нет данных |
| Эксплойт | используется в атаках |
| Идентификаторы | PT-2026-65062, CVE-2026-63077, PT-2026-70005, BDU:2026-11246, CVE-2026-72529 |
| CVSS | 9.8 |
| CWE | CWE-502 |
| Последствия | нет данных |
| Сверено по базам | CVE-2026-63077: CISA KEV с 05.08.2026, устранить до 08.08.2026; EPSS 89,6%; CVE-2026-72529: CISA KEV с 20.08.2026, устранить до 23.08.2026; EPSS 1,5%; нет в справочных базах: PT-2026-65062, PT-2026-70005 |

**Почему важно:** Интерес «Уязвимости и обновления безопасности»: ключевые слова: уязвимость, CVE.

Также об этом: [Positive Technologies: новости](https://ptsecurity.com/about/news/pt-has-released-its-sept-digest-of-trending-vulnerabilities)

### [Контроллеры Johnson Controls EasyIO Neo допускают утечку учётных данных через HTTP и отладочные порты](https://1275.ru/vulnerability/kontrollery-johnson-controls-easyio-neo-dopuskayut-utechku-uchyotnyh-dannyh-cherez-http-i-otladochnye-porty_42663)

*1275.ru: уязвимости и индикаторы · 02.10.2026 · Уязвимость · приоритет: средний (эксплойт: нет данных) · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

Две уязвимости в контроллерах Johnson Controls EasyIO Neo Series EC и CW дают постороннему доступ к чувствительным сведениям, которые устройства передают по сети и хранят внутри. Одна проблема связана с передачей данных в открытом виде, вторая - с раскрытием служебной информации неавторизованному лицу. Обе затрагивают оборудование, управляющее отоплением, вентиляцией…

| Поле | Значение |
| --- | --- |
| Уязвимость | нет данных |
| Затронуто | нет данных |
| Обновление | нет данных |
| Временные меры | нет данных |
| Эксплойт | нет данных |
| Идентификаторы | CVE-2026-64893, CVE-2026-64892 |
| CVSS | 5.4 |
| CWE | нет данных |
| Последствия | нет данных |
| Сверено по базам | CVE-2026-64893: EPSS 0,1%; CVE-2026-64892: EPSS 0,2% |

**Почему важно:** Интерес «Безопасность АСУ ТП и промышленных систем»: ключевые слова: ICS, OT, Modbus, промышленная автоматизация.

Также об этом: [CISA ICS Advisories](https://cisa.gov/news-events/ics-advisories/icsa-26-274-04)

### [Positive Technologies помогла исправить 17 уязвимостей в популярной российской SCADA-системе](https://safe.cnews.ru/news/line/2026-10-01_positive_technologies_pomogla_ispravit)

*CNews: Безопасность · 01.10.2026 · Уязвимость · приоритет: средний (эксплойт: нет данных) · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

Компания «Каскад-АСУ» поблагодарила экспертов PT SWARM за обнаружение 17 уязвимостей в двух компонентах SCADA-системы...

| Поле | Значение |
| --- | --- |
| Уязвимость | нет данных |
| Затронуто | нет данных |
| Обновление | нет данных |
| Временные меры | нет данных |
| Эксплойт | нет данных |
| Идентификаторы | BDU:2026-01678, BDU:2026-01682, BDU:2026-01676, BDU:2026-01677, BDU:2026-01683 |
| CVSS | нет данных |
| CWE | нет данных |
| Последствия | нет данных |

**Почему важно:** Интерес «Безопасность АСУ ТП и промышленных систем»: ключевые слова: АСУ ТП, SCADA.

*Нет в тексте статьи, убрано проверкой: Оценка CVSS.*

Также об этом: [CNews](https://cnews.ru/news/line/2026-10-01_positive_technologies_pomogla_ispravit)

### [Meari IoT Cloud Platform OpenAPI Service](https://cisa.gov/news-events/ics-advisories/icsa-26-274-06)

*CISA ICS Advisories · 01.10.2026 · Уязвимость · приоритет: средний (эксплойт: нет данных) · релевантность 0.99 · интерес: Безопасность АСУ ТП и промышленных систем*

View CSAF Summary Successful exploitation of these vulnerabilities could allow attackers to manipulate device configurations, trigger unauthorized behaviors, and access sensitive information such as device credentials, owner details, and network data without proper authorization. The following versions of Meari IoT Cloud Platform OpenAPI Service are affected: IoT Cloud…

| Поле | Значение |
| --- | --- |
| Уязвимость | нет данных |
| Затронуто | нет данных |
| Обновление | нет данных |
| Временные меры | нет данных |
| Эксплойт | нет данных |
| Идентификаторы | CVE-2026-101104, CVE-2026-96613 |
| CVSS | 3.1 (CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:N/I:H/A:N) |
| Доступ | по сети |
| Сложность | низкая |
| Права | низкие |
| Действия пользователя | не нужны |
| CWE | CWE-862 |
| Последствия | нет данных |
| Сверено по базам | CVE-2026-101104: EPSS 0,3%; CVE-2026-96613: EPSS 0,2% |

**Почему важно:** Интерес «Безопасность АСУ ТП и промышленных систем»: близость по содержанию.

### [Nozomi identifies 19 vulnerabilities in Pepperl+Fuchs IO-Link Master enabling root access and OT attacks](https://industrialcyber.co/threats-attacks/nozomi-identifies-19-vulnerabilities-in-pepperlfuchs-io-link-master-enabling-root-access-and-ot-attacks)

*Industrial Cyber · 29.09.2026 · Уязвимость · приоритет: средний (эксплойт: нет данных) · релевантность 0.96 · интерес: Безопасность АСУ ТП и промышленных систем*

Researchers from Nozomi Networks Labs identified 19 vulnerabilities in the Pepperl+Fuchs IO-Link Master ICE2-8IOL-K45P-RJ45 running EtherNet/IP firmware version... The post Nozomi identifies 19 vulnerabilities in Pepperl+Fuchs IO-Link Master enabling root access and OT attacks appeared first on Industrial Cyber .

| Поле | Значение |
| --- | --- |
| Уязвимость | нет данных |
| Затронуто | нет данных |
| Обновление | нет данных |
| Временные меры | нет данных |
| Эксплойт | нет данных |
| Идентификаторы | CVE-2026-27546 |
| CVSS | нет данных |
| CWE | нет данных |
| Последствия | нет данных |
| Сверено по базам | CVE-2026-27546: EPSS 1,0% |

**Почему важно:** Интерес «Безопасность АСУ ТП и промышленных систем»: ключевые слова: OT.

### [Обновление БДУ](https://t.me/bdufstecru/3488)

*БДУ ФСТЭК России · 30.09.2026 · Уязвимость · приоритет: средний (эксплойт: нет данных) · релевантность 0.90 · интерес: Требования регуляторов по ИБ*

Обновлены сведения об уязвимостях программного обеспечения Добавлена информация о 178 уязвимостях программного обеспечения Внесены изменения в 366 записей об уязвимостях программного обеспечения 🔶БДУ ФСТЭК России в MAX

| Поле | Значение |
| --- | --- |
| Уязвимость | нет данных |
| Затронуто | нет данных |
| Обновление | нет данных |
| Временные меры | нет данных |
| Эксплойт | нет данных |
| Идентификаторы | нет данных |
| CVSS | нет данных |
| CWE | нет данных |
| Последствия | нет данных |

**Почему важно:** Интерес «Требования регуляторов по ИБ»: ключевые слова: ФСТЭК.

## 3. Требования регуляторов по ИБ

### [ФСТЭК разъяснила порядок и сроки представления результатов оценки защищённости информационных систем](https://1275.ru/compliance/fstek-razyasnila-poryadok-i-sroki-predstavleniya-rezultatov-otsenki-zaschischyonnosti-informatsionnyh-sistem_42689)

*1275.ru: уязвимости и индикаторы · 02.10.2026 · релевантность 1.00 · интерес: Требования регуляторов по ИБ*

1 октября 2026 года ФСТЭК России опубликовала информационное сообщение N 240/92/6722. Оно касается показателя, характеризующего текущее состояние защиты информации от базового уровня угроз безопасности. Рассчитывать его обязаны операторы и обладатели информации государственных информационных систем, а также иных систем государственных органов, унитарных предприятий и…

**Почему важно:** Интерес «Требования регуляторов по ИБ»: ключевые слова: ФСТЭК.

### [Аттестация и практика работы по приказу ФСТЭК 117](https://habr.com/ru/companies/selectel/articles/1078612)

*Хабр: Информационная безопасность · 28.09.2026 · релевантность 1.00 · интерес: Требования регуляторов по ИБ*

Привет, Хабр! На связи Алёна, аналитик по информационной безопасности в Selectel . В последние пять лет вышло множество нормативно‑правовых актов от ФСТЭК России, которые кардинально изменили как подход к защите государственных информационных систем (далее — ГИС), так и порядок их аттестации и последующей эксплуатации. Так как все эти регламенты выходили последовательно, и на…

**Почему важно:** Интерес «Требования регуляторов по ИБ»: ключевые слова: ФСТЭК.

### [Спикател и ГК «Инфобезопасность» объявили об информационном партнёрстве](https://infobezopasnost.ru/blog/news/spikatel-i-gk-infobezopasnost-obyavili-ob-informatsionnom-partnyorstve)

*Инфобезопасность · 01.10.2026 · релевантность 0.99 · интерес: Требования регуляторов по ИБ*

ГК «Инфобезопасность» — группа компаний в сфере защиты информации. Учебный центр работает с 2014 года: программы профессиональной переподготовки и повышения квалификации по ИБ согласованы с ФСБ и ФСТЭК России. Стороны рассчитывают, что регулярный обмен информацией и освещение совместных инициатив помогут сделать знания о кибербезопасности доступнее для специалистов и бизнеса.…

**Почему важно:** Интерес «Требования регуляторов по ИБ»: ключевые слова: ФСТЭК, ФСБ.

### [«Лаборатория Касперского» присвоила Т1 Интеграция партнёрский статус по технической специализации KICS](https://www.kaspersky.ru/about/press-releases/laboratoriya-kasperskogo-prisvoila-t1-integraciya-partnyorskij-status-po-tehnicheskoj-specializacii-kics)

*Лаборатория Касперского: пресс-релизы · 25.09.2026 · релевантность 0.96 · интерес: Безопасность АСУ ТП и промышленных систем*

Партнёр подтвердил экспертизу в работе с Kaspersky Industrial CyberSecurity Т1 Интеграция подтвердила экспертизу в работе с Kaspersky Industrial CyberSecurity — XDR-платформой для комплексной защиты промышленных инфраструктур. Полученная специализация позволяет выполнять комплексные проекты по защите АСУ ТП для заказчиков из топливно-энергетического комплекса и промышленности.

**Почему важно:** Интерес «Безопасность АСУ ТП и промышленных систем»: ключевые слова: АСУ ТП.

### [Госзакупки российского ПО перекраивают рынок: антивирусных поставщиков стало на 18% меньше](https://securitymedia.org/news/goszakupki-rossiyskogo-po-perekraivayut-rynok-antivirusnykh-postavshchikov-stalo-na-18-menshe.html)

*SecurityMedia · 02.10.2026 · релевантность 0.95 · интерес: Требования регуляторов по ИБ*

По итогам трех кварталов 2026 года число поставщиков антивирусного ПО в российских госзакупках сократилось на 18% год к году. Одновременно рынок видеоконференцсвязи просел еще на 13%, хотя годом ранее падение достигало 34%.

**Почему важно:** Интерес «Требования регуляторов по ИБ»: ключевые слова: ФСТЭК, ФСБ, импортозамещение, сертификация.

### [«Цифровые решения» и Positive Technologies усилили мониторинг кибербезопасности энергетического холдинга](https://habr.com/ru/companies/dsol/news/1087934)

*Хабр: новости ИБ · 29.09.2026 · релевантность 0.85 · интерес: Атаки на энергетику и критическую инфраструктуру*

Компании «Цифровые решения» и Positive Technologies реализовали проект по созданию масштабируемой системы мониторинга кибербезопасности в крупном энергетическом холдинге. Совместное решение включает брокер сетевых пакетов DS Integrity, систему обеспечения киберустойчивости промышленных инфраструктур PT ISIM и систему поведенческого анализа сетевого трафика PT Network Attack…

**Почему важно:** Интерес «Атаки на энергетику и критическую инфраструктуру»: ключевые слова: энергетика.

## 4. Безопасность АСУ ТП и промышленных систем

### [One Packet Can Crash OT Servers in Industrial Sectors](https://darkreading.com/ics-ot-security/one-packet-crash-servers-tdengine)

*Dark Reading · 29.09.2026 · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

A high-severity zero-day vulnerability affects the TDengine time-series database used across industrial, IoT, energy, and automotive environments.

**Почему важно:** Интерес «Безопасность АСУ ТП и промышленных систем»: ключевые слова: OT.

### [How decades of disconnected modernization created OT security debt manufacturers can’t escape](https://industrialcyber.co/features/how-decades-of-disconnected-modernization-created-ot-security-debt-manufacturers-cant-escape)

*Industrial Cyber · 29.09.2026 · релевантность 0.95 · интерес: Безопасность АСУ ТП и промышленных систем*

The OT security crisis facing manufacturers today is fundamentally a debt crisis, accumulated over decades as systems grew... The post How decades of disconnected modernization created OT security debt manufacturers can’t escape appeared first on Industrial Cyber .

**Почему важно:** Интерес «Безопасность АСУ ТП и промышленных систем»: ключевые слова: OT, Modbus.

### [Alliance for Critical Infrastructure expands membership across US sectors to address evolving cyber, physical threats](https://industrialcyber.co/critical-infrastructure/alliance-for-critical-infrastructure-expands-membership-across-us-sectors-to-address-evolving-cyber-physical-threats)

*Industrial Cyber · 02.10.2026 · релевантность 0.94 · интерес: Атаки на энергетику и критическую инфраструктуру*

The Alliance for Critical Infrastructure (ACI) expanded its membership to nearly 50 companies across six U.S. critical infrastructure... The post Alliance for Critical Infrastructure expands membership across US sectors to address evolving cyber, physical threats appeared first on Industrial Cyber .

**Почему важно:** Интерес «Атаки на энергетику и критическую инфраструктуру»: ключевые слова: critical infrastructure.

<details><summary>Не вошло в выпуск: 40</summary>

- [Positive Technologies помогла исправить 17 уязвимостей в популярной российской SCADA-системе](https://cnews.ru/news/line/2026-10-01_positive_technologies_pomogla_ispravit) · CNews · оценка 1.00 · повтор уже включённой новости
- [Johnson Controls EasyIO Neo Series EC and CW Controllers](https://cisa.gov/news-events/ics-advisories/icsa-26-274-04) · CISA ICS Advisories · оценка 1.00 · повтор уже включённой новости
- [August 2026 Threat Trend Report on APT Attacks (South Korea)](https://asec.ahnlab.com/en/95649) · AhnLab ASEC · оценка 0.85 · не вошла в лимит выпуска
- [Спуфинг кампания CaptiveCrunch: отпуск с «трояном в кармане» или как отельный Wi‑Fi может стать точкой кражи данных](https://habr.com/ru/articles/1087460) · Хабр: Информационная безопасность · оценка 0.85 · не вошла в лимит выпуска
- [Fortinet предупреждает о критической уязвимости, которая активно используется в 0-day атаках для выполнения несанкционированного кода или команд на уязвимых устройствах](https://t.me/true_secator/8672) · SecAtor · оценка 0.82 · не вошла в лимит выпуска
- [Positive Technologies представила сентябрьский дайджест трендовых уязвимостей](https://ptsecurity.com/about/news/pt-has-released-its-sept-digest-of-trending-vulnerabilities) · Positive Technologies: новости · оценка 0.81 · повтор уже включённой новости
- [Минцифры вынесло Антифрод 3.0 на обсуждение: что предлагают изменить для SIM-карт, сайтов и Госуслуг](https://securitylab.ru/news/578108.php) · SecurityLab.ru · оценка 0.81 · не вошла в лимит выпуска
- [D-Link «расследует» информацию о двух критических уязвимостях в роутерах](https://safe.cnews.ru/news/top/2026-09-28_d-link_rassleduet_informatsiyu) · CNews: Безопасность · оценка 0.81 · не вошла в лимит выпуска
- [Cisco выпустила обновления для устранения критической 0-day в Catalyst SD-WAN Manager (отслеживаемой как CVE-2026-76504), которую злоумышленники активно используют для повышения…](https://t.me/true_secator/8666) · SecAtor · оценка 0.79 · не вошла в лимит выпуска
- [Российским БПЛА облегчат жизнь. Власти снизят требования к локализации батарей](https://cnews.ru/news/top/2026-10-01_batarei_dlya_bpla_vydelyat) · CNews · оценка 0.79 · не вошла в лимит выпуска
- [Продолжаем отслеживать трендовые угрозы и на текущий момент выделим следующие](https://t.me/true_secator/8670) · SecAtor · оценка 0.78 · не вошла в лимит выпуска
- [Импортозамещение 2026: от экстренных замен к устойчивой архитектуре — итоги конференции TAdviser](https://tadviser.ru/a/968494) · TAdviser · оценка 0.77 · не вошла в лимит выпуска
- [Netscaler снова под прицелом: вышли исправления для двух 0Day](https://t.me/ZerodayAlert/854) · ZeroDay Alert · оценка 0.77 · повтор уже включённой новости
- [Cisco warns of new SD-WAN zero-day exploited in attacks](https://bleepingcomputer.com/news/security/cisco-warns-of-new-sd-wan-authentication-bypass-zero-day-exploited-in-attacks) · BleepingComputer · оценка 0.77 · повтор уже включённой новости
- [ОБЭП (ОЭБ) на пороге IT‑компании: как защитить исходный код, сервера и блокчейн‑решения при обследовании и обыске](https://habr.com/ru/articles/1088850) · Хабр: Информационная безопасность · оценка 0.77 · не вошла в лимит выпуска
- [Apple выпустила обновления для устранения 0-day, используемой в «чрезвычайно сложных» таргетированных атаках на устройства iOS](https://t.me/true_secator/8656) · SecAtor · оценка 0.76 · не вошла в лимит выпуска
- [Hackers exploit Citrix NetScaler zero-day to deploy web shells](https://bleepingcomputer.com/news/security/hackers-exploit-citrix-netscaler-zero-day-to-deploy-web-shells) · BleepingComputer · оценка 0.76 · повтор уже включённой новости
- [Опубликованы новые результаты тестирования обновлений ПО](https://t.me/bdufstecru/3492) · БДУ ФСТЭК России · оценка 0.75 · не вошла в лимит выпуска
- [Apple patches CoreGraphics zero-day flaw exploited in attacks](https://bleepingcomputer.com/news/security/apple-patches-coregraphics-zero-day-flaw-exploited-in-attacks) · BleepingComputer · оценка 0.75 · повтор уже включённой новости
- [Defending Against Active Exploitation of Citrix NetScaler ADC and Gateway Appliances](https://cloud.google.com/blog/topics/threat-intelligence/defending-against-active-exploitation-of-citrix-netscaler-adc-and-gateway-appliances) · Google Cloud: Threat Intelligence · оценка 0.74 · повтор уже включённой новости
- [Warning: Two Unpatched Citrix NetScaler RCE Zero-Days Under Active Exploitation](https://thehackernews.com/2026/09/warning-two-unpatched-citrix-netscaler.html) · The Hacker News · оценка 0.73 · не вошла в лимит выпуска
- [Custom malware used in Citrix 0-day attacks targeting govt, banks, professional services](https://theregister.com/security/2026/09/29/custom-malware-used-in-citrix-0-day-attacks-targeting-govt-banks-professional-services/5299867) · The Register: Security · оценка 0.73 · повтор уже включённой новости
- [Кибербезопасность нового времени: что обсудят на KDW 2026](https://securitylab.ru/news/578191.php) · SecurityLab.ru · оценка 0.72 · не вошла в лимит выпуска
- [Получен сертификат ФСТЭК России на средство многофакторной аутентификации MFA JaCarta-3](https://cnews.ru/news/line/2026-09-29_poluchen_sertifikat_fstek) · CNews · оценка 0.72 · не вошла в лимит выпуска
- [Власти проверят российские заводы на тайную подмену плат китайскими](https://cnews.ru/news/top/2026-09-28_elektroniku_budut_proveryat) · CNews · оценка 0.72 · не вошла в лимит выпуска
- [Fortinet warns of critical FortiMail flaw exploited in zero-day attacks](https://bleepingcomputer.com/news/security/fortinet-warns-of-critical-fortimail-flaw-exploited-in-zero-day-attacks) · BleepingComputer · оценка 0.72 · повтор уже включённой новости
- [Что происходит с продуктом, когда разработчик решает пройти сертификацию ФСТЭК](https://habr.com/ru/companies/multifactor/articles/1088414) · Хабр: Информационная безопасность · оценка 0.72 · не вошла в лимит выпуска
- [Toptech TMS7 and TopHAT](https://cisa.gov/news-events/ics-advisories/icsa-26-272-02) · CISA ICS Advisories · оценка 0.72 · не вошла в лимит выпуска
- [Минцифры представило третий пакет мер по борьбе с кибермошенничеством](https://habr.com/ru/news/1088634) · Хабр: новости ИБ · оценка 0.72 · не вошла в лимит выпуска
- [Критическая уязвимость обхода аутентификации в WSO2 API Manager (CVE-2026-5430)](https://t.me/cyberok_news/260) · CyberOK · оценка 0.71 · не вошла в лимит выпуска
- [Lantronix G520 Series Cellular Gateway](https://cisa.gov/news-events/ics-advisories/icsa-26-272-01) · CISA ICS Advisories · оценка 0.71 · не вошла в лимит выпуска
- [CISA добавила в каталог активно эксплуатируемых уязвимостей обход пути в Fortinet FortiMail](https://1275.ru/vulnerability/cisa-dobavila-v-katalog-aktivno-ekspluatiruemyh-uyazvimostey-obhod-puti-v-fortinet-fortimail_42640) · 1275.ru: уязвимости и индикаторы · оценка 0.71 · повтор уже включённой новости
- [Как приоритизировать новости об уязвимостях вместо балла CVSS](https://habr.com/ru/articles/1086358) · Хабр: Системное администрирование · оценка 0.71 · не вошла в лимит выпуска
- [Три магнитофона, три кинокамеры: сколько у вас на самом деле иностранного ПО](https://habr.com/ru/companies/simpleone/articles/1087848) · Хабр: Информационная безопасность · оценка 0.71 · не вошла в лимит выпуска
- [Более сотни уязвимостей в четырёх продуктах Kiteworks открывают путь к захвату учётных записей и выполнению кода](https://1275.ru/vulnerability/bolee-sotni-uyazvimostey-v-chetyryoh-produktah-kiteworks-otkryvayut-put-k-zahvatu-uchyotnyh-zapisey-i-vypolneniyu-koda_42644) · 1275.ru: уязвимости и индикаторы · оценка 0.70 · не вошла в лимит выпуска
- [ViPNet EDI Soap Gate 3 в реестрах Минпромторга России](https://safe.cnews.ru/news/line/2026-10-01_vipnet_edi_soap_gate_3_v_reestrah_minpromtorga) · CNews: Безопасность · оценка 0.70 · не вошла в лимит выпуска
- [Тренд на ИИ и комплексную защиту: как меняется ситуация на рынке госзакупок ИТ в России](https://cnews.ru/news/line/2026-10-01_trend_na_ii_i_kompleksnuyu) · CNews · оценка 0.70 · не вошла в лимит выпуска
- [Vulnerability Discovery and Exploitation Trends in the AI Era](https://cloud.google.com/blog/topics/threat-intelligence/vulnerability-discovery-and-exploitation-trends-in-the-ai-era) · Google Cloud: Threat Intelligence · оценка 0.70 · не вошла в лимит выпуска
- [Ирония судьбы](https://t.me/alukatsky/15355) · Пост Лукацкого · оценка 0.69 · не вошла в лимит выпуска
- [Cisco Patches Exploited Catalyst SD-WAN Zero-Day Vulnerability](https://securityweek.com/cisco-patches-exploited-catalyst-sd-wan-zero-day-vulnerability) · SecurityWeek · оценка 0.69 · не вошла в лимит выпуска

</details>

---

## Как составлен выпуск

- Публикаций за период: 1716. Кандидатов после поиска по интересам: 60. В выпуске: 20 из 14 источников.
- Поиск: ollama:embeddinggemma:300m. Оценка и тексты: heuristic.
- Пересказов одной новости объединено: 7.
- Приоритеты атак и уязвимостей по правилам датасета организаторов: высокий 4, средний 7, низкий 0.
- Проверка записей по тексту статей: исправлено записей 1, убрано полей и фраз 1.
