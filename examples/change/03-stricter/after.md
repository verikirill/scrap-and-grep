---
profile: "Специалист по ИБ АСУ ТП (03-stricter)"
profile_version: 1
audience: "specialist"
period_start: "2026-09-25"
period_end: "2026-10-02"
generated: "2026-10-23T22:14+03:00"
llm: "openai:qwen3.6-35b-a3b/latest"
embedding: "openai:text-embeddings-v2-doc/latest"
sources: 7
publications: 1807
candidates: 60
entries: 10
manual_minutes: 85
---

# Атаки на АСУ ТП и критические уязвимости в промышленном оборудовании

**Профиль:** Специалист по ИБ АСУ ТП (03-stricter) (версия 1)  
**Период:** 25.09.2026 - 02.10.2026  
**Сформирован:** 23.10.2026 22:14 МСК

*Вместо ручной работы: ассистент просмотрел 1 807 публикаций и написал 10 записей за 2 с; вручную это около 85 мин по журналу аналитика ИБ: 1,3 с на публикацию и 4,6 мин на запись.*

## Содержание

- [1. Атаки](#1-атаки)
- [2. Уязвимости](#2-уязвимости)
- [3. ФСТЭК уточнила сроки оценки ИС](#3-фстэк-уточнила-сроки-оценки-ис)

## Главное

- Иранская группировка CyberAv3ngers атакует системы водоснабжения США через уязвимые ПЛК.
- Уязвимости в ABB PCM600, Armatura One, Meari IoT и IO-Link Master Pepperl+Fuchs позволяют получить полный контроль над оборудованием.
- Уязвимость нулевого дня в TDengine позволяет завершить работу OT-серверов.
- CISA добавила уязвимости в Microsoft SharePoint и Mikrotik RouterOS в каталог KEV.
- ФСТЭК уточнила порядок и сроки представления результатов оценки защищённости информационных систем.

## План на смену

- [ ] [Уязвимости в системе управления доступом Armatura One](https://cisa.gov/news-events/ics-advisories/icsa-26-274-01)
  - Обновление: выпущено, версии 4.7.2 и 4.6.1_USA
  - Временные меры: Ограничить доступ к порту OpenWire протокола Apache ActiveMQ.
  - в каталоге CISA KEV с 02.11.2023, устранить до 23.11.2023; EPSS 99,9%; CVSS 9.8; эксплойт: используется в атаках
- [ ] [CISA добавила в каталог KEV уязвимости в Microsoft SharePoint и Mikrotik RouterOS](https://cisa.gov/news-events/alerts/2026/09/25/cisa-adds-two-known-exploited-vulnerabilities-catalog)
  - Устранение по БДУ: обновление программного обеспечения
  - в каталоге CISA KEV с 25.09.2026, устранить до 28.09.2026; EPSS 2,1%; CVSS 8.8; эксплойт: используется в атаках
- [ ] [Уязвимости в Meari IoT Cloud Platform OpenAPI Service](https://cisa.gov/news-events/ics-advisories/icsa-26-274-06)
  - Временные меры: Изолируйте сети управления и удалённые устройства за межсетевыми экранами, минимизируйте сетевое воздействие, используйте защищённые методы удалённого доступа.
  - Обновление: исправлений нет
  - EPSS 0,3%; CVSS 7.7; эксплойт: есть публичный эксплойт
- [ ] [Уязвимости в ABB PCM600 позволяют повысить привилегии и записать файлы](https://cisa.gov/news-events/ics-advisories/icsa-26-274-03)
  - Временные меры: Настройте службу ABBPCMSchedulerService на запуск под тем же аккаунтом Windows, что и приложение PCM600. Включите Always trust IED security certificates только в доверенной среде.
  - EPSS 0,1%; CVSS 6.4; эксплойт: есть публичный эксплойт

## 1. Атаки

Низкий приоритет: 1. Порядок по правилу: атаки на ТЭК и промышленность РФ приоритетнее других отраслей РФ, зарубежные инциденты - в конце.

### [Иранская группировка CyberAv3ngers атаковала системы водоснабжения США через уязвимые PLC](https://t.me/alukatsky/15356)

*Пост Лукацкого · 02.10.2026 · Атака · приоритет: низкий (вне РФ или страна не названа) · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

Оригинал: На KazHackStan я слушал выступление Дениса Ласкова про атаки на критическую инфраструктуру и зацепила меня одна история

Группировка CyberAv3ngers использовала уязвимости в контроллерах Unitronics PLC и Rockwell/Allen-Bradley MicroLogix для атак на объекты водоснабжения США, что привело к физическим сбоям и риску загрязнения воды. Злоумышленники получали прямой доступ к оборудованию через интернет, изменяя конфигурации и отключая сигнализацию без проникновения в корпоративную сеть.

| Поле | Значение |
| --- | --- |
| Страна жертвы | США |
| Группировка | CyberAv3ngers |
| Дата атаки | 2023-2026 |
| Отрасли и компании | Системы водоснабжения, муниципалитеты |
| Вектор атаки | Уязвимость на периметре |
| Первоначальный доступ | Прямой доступ к PLC, выставленным в интернет |
| Затронутые продукты | Unitronics PLC, Rockwell/Allen-Bradley MicroLogix 1100/1400 |
| Инструменты | нет данных |
| Уязвимости | нет данных |
| Техники ATT&CK | нет данных |
| Индикаторы компрометации | нет |

**Почему важно:** Закройте доступ к промышленным контроллерам из интернета и проверьте наличие не зашифрованных паролей на Unitronics PLC и Rockwell MicroLogix.

## 2. Уязвимости

Высокий приоритет: 4; средний приоритет: 4. Порядок по правилу: уязвимости с известным эксплойтом показываются первыми.

### [Уязвимости в ABB PCM600 позволяют повысить привилегии и записать файлы](https://cisa.gov/news-events/ics-advisories/icsa-26-274-03)

*CISA ICS Advisories · касается нас: ABB PCM600 · 01.10.2026 · Уязвимость · приоритет: высокий (эксплойт: есть публичный эксплойт) · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

Оригинал: ABB Protection and Control IED Manager PCM600

Эксплуатация уязвимостей в ABB Protection and Control IED Manager PCM600 позволяет злоумышленнику с локальным доступом повысить привилегии до уровня LocalSystem и записывать файлы за пределами целевых директорий.

| Поле | Значение |
| --- | --- |
| Уязвимость | уязвимость в ABB Protection and Control IED Manager PCM600 |
| Затронуто | ABB Protection and Control IED Manager PCM600 \<=2.14 |
| Обновление | нет данных |
| Временные меры | Настройте службу ABBPCMSchedulerService на запуск под тем же аккаунтом Windows, что и приложение PCM600. Включите Always trust IED security certificates только в доверенной среде. |
| Эксплойт | есть публичный эксплойт |
| Идентификаторы | CVE-2026-15952, CVE-2026-15953 |
| CVSS | 6.4 (CVSS:3.1/AV:L/AC:H/PR:H/UI:N/S:U/C:H/I:H/A:H) |
| Доступ | локально |
| Сложность | высокая |
| Права | высокие |
| Действия пользователя | не нужны |
| CWE | CWE-732 |
| Последствия | повышение привилегий, запись файлов |
| Оборудование | ABB Protection and Control IED Manager PCM600 |
| Сверено по базам | CVE-2026-15952: EPSS 0,1%; CVSS 6.4 по NVD; CVE-2026-15953: EPSS 0,1%; CVSS 5 по NVD |

**Почему важно:** Закройте доступ к PCM600 из интернета и настройте службу ABBPCMSchedulerService на запуск под тем же аккаунтом Windows, что и само приложение.

### [Две уязвимости в CODESYS позволяют вызвать отказ в обслуживании и исказить данные мониторинга](https://1275.ru/vulnerability/dve-uyazvimosti-v-codesys-pozvolyayut-vyzvat-otkaz-v-obsluzhivanii-i-iskazit-dannye-monitoringa_42653)

*1275.ru: уязвимости и индикаторы · касается нас: CODESYS · 02.10.2026 · Уязвимость · приоритет: средний (эксплойт: нет) · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

Уязвимости в компонентах CODESYS позволяют злоумышленнику вызвать отказ в обслуживании через исчерпание памяти или исказить данные мониторинга, сделав поведение контроллера непредсказуемым.

| Поле | Значение |
| --- | --- |
| Уязвимость | уязвимости в CODESYS |
| Затронуто | CODESYS Development System 3, CODESYS Gateway, Edge Gateway (Windows/Linux), HMI, OPC DA, PLCHandler, Runtime Toolkit, CODESYS Control (Linux, ARM, Raspberry Pi, Beckhoff CX, PFC100, PFC200, PLCnext, WAGO Touch Panels 600, Virtual Control SL, Safety SIL2) |
| Обновление | выпущено, версия 3.5.22.40; для Edge Gateway для Linux и ряда встраиваемых систем выпущено, версия 4.23.0.0. Для части версий исправление ещё не выпущено. |
| Временные меры | Ограничить доступ к веб-консоли и шлюзам. Не подключать несколько систем одновременно к одному контроллеру. |
| Эксплойт | нет |
| Идентификаторы | CVE-2026-76992, CVE-2026-79625 |
| CVSS | 8.1 |
| CWE | нет данных |
| Последствия | отказ в обслуживании, искажение данных мониторинга, непредсказуемое поведение контроллера |
| Протоколы | OPC DA |
| Сверено по базам | CVE-2026-76992: EPSS 0,3%; CVSS 7.5 по NVD; CVE-2026-79625: EPSS 0,2%; CVSS 8.1 по NVD |

**Почему важно:** Закройте доступ к шлюзам и панелям оператора из интернета. Обновите среды исполнения до версий 3.5.22.40 и 4.23.0.0, если они доступны.

### [Уязвимости в системе управления доступом Armatura One](https://cisa.gov/news-events/ics-advisories/icsa-26-274-01)

*CISA ICS Advisories · 01.10.2026 · Уязвимость · приоритет: высокий (эксплойт: используется в атаках) · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

Оригинал: Armatura LLC Armatura One

Злоумышленник может получить несанкционированный доступ к базе данных, выполнить произвольный код с правами администратора или перехватить контроль над системой физического доступа.

| Поле | Значение |
| --- | --- |
| Уязвимость | уязвимости в Armatura One |
| Затронуто | Armatura One \<4.7.2, Armatura One (USA) \<4.6.1 |
| Обновление | выпущено, версии 4.7.2 и 4.6.1_USA |
| Временные меры | Ограничить доступ к порту OpenWire протокола Apache ActiveMQ. |
| Эксплойт | используется в атаках |
| Идентификаторы | CVE-2023-46604, CVE-2026-94591, CVE-2026-94592, CVE-2026-94593, CVE-2026-94594 |
| CVSS | 9.8 (CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H) |
| Доступ | по сети |
| Сложность | низкая |
| Права | не нужны |
| Действия пользователя | не нужны |
| CWE | CWE-502 |
| Последствия | удалённое выполнение кода, несанкционированный доступ к БД, контроль системы физического доступа |
| Оборудование | Armatura LLC Armatura One |
| Протоколы | OpenWire |
| Сверено по базам | CVE-2023-46604: CISA KEV с 02.11.2023, устранить до 23.11.2023; CISA SSVC: эксплуатируется; публичный эксплойт по NVD; EPSS 99,9%; CVSS 9.8 по NVD; CVE-2026-94591: EPSS 0,1%; CVSS 8.4 по NVD; CVE-2026-94592: EPSS 0,1%; CVSS 8.4 по NVD; CVE-2026-94593: EPSS 0,1%; CVSS 7.8 по NVD; CVE-2026-94594: EPSS 0,1%; CVSS 4 по NVD |

**Почему важно:** Закройте порты OpenWire от внешних сетей на АСУ ТП подстанциях и обновите Armatura One до версий 4.7.2 и 4.6.1_USA.

### [Уязвимости в Meari IoT Cloud Platform OpenAPI Service](https://cisa.gov/news-events/ics-advisories/icsa-26-274-06)

*CISA ICS Advisories · 01.10.2026 · Уязвимость · приоритет: высокий (эксплойт: есть публичный эксплойт) · релевантность 0.92 · интерес: Безопасность АСУ ТП и промышленных систем*

Оригинал: Meari IoT Cloud Platform OpenAPI Service

Злоумышленник может изменять конфигурации чужих устройств и получать доступ к их теневым копиям, включая учётные данные и сетевые данные.

| Поле | Значение |
| --- | --- |
| Уязвимость | уязвимости в Meari IoT Cloud Platform OpenAPI Service |
| Затронуто | Meari IoT Cloud Platform OpenAPI Service vers:all/* |
| Обновление | исправлений нет |
| Временные меры | Изолируйте сети управления и удалённые устройства за межсетевыми экранами, минимизируйте сетевое воздействие, используйте защищённые методы удалённого доступа. |
| Эксплойт | есть публичный эксплойт |
| Идентификаторы | CVE-2026-101104, CVE-2026-96613 |
| CVSS | 7.7 (CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:N/I:H/A:N) |
| Доступ | по сети |
| Сложность | низкая |
| Права | низкие |
| Действия пользователя | не нужны |
| CWE | CWE-862 |
| Последствия | несанкционированное изменение конфигураций устройств, утечка учётных данных и сетевой информации |
| Оборудование | Meari IoT Cloud Platform OpenAPI Service |
| Сверено по базам | CVE-2026-101104: EPSS 0,3%; CVSS 7.7 по NVD; CVE-2026-96613: EPSS 0,2%; CVSS 6.5 по NVD |

**Почему важно:** Закройте доступ к IoT-шлюзам из интернета и изолируйте их за межсетевыми экранами.

### [CISA добавила в каталог KEV уязвимости в Microsoft SharePoint и Mikrotik RouterOS](https://cisa.gov/news-events/alerts/2026/09/25/cisa-adds-two-known-exploited-vulnerabilities-catalog)

*CISA: оповещения и каталог KEV · 25.09.2026 · Уязвимость · приоритет: высокий (эксплойт: используется в атаках) · релевантность 0.92 · интерес: Уязвимости и обновления безопасности*

Оригинал: CISA Adds Two Known Exploited Vulnerabilities to Catalog

CISA подтвердила активную эксплуатацию уязвимостей CVE-2026-65660 (код-инъекция в SharePoint) и CVE-2026-67279 (нарушение рабочего процесса в RouterOS). Эти уязвимости представляют высокий риск для инфраструктуры.

| Поле | Значение |
| --- | --- |
| Уязвимость | уязвимости в Microsoft SharePoint и Mikrotik RouterOS |
| Затронуто | Microsoft SharePoint, Mikrotik RouterOS |
| Обновление | нет данных |
| Временные меры | нет данных |
| Эксплойт | используется в атаках |
| Идентификаторы | CVE-2026-65660, CVE-2026-67279 |
| CVSS | нет данных |
| CWE | нет данных |
| Последствия | удаленное выполнение кода, полный контроль над активом |
| Сверено по базам | CVE-2026-65660: CISA KEV с 25.09.2026, устранить до 28.09.2026; BDU:2026-15539, эксплойт существует в открытом доступе, используется в атаках; CISA SSVC: эксплуатируется; EPSS 2,1%; CVE-2026-67279: CISA KEV с 25.09.2026, устранить до 28.09.2026; BDU:2026-14710, эксплойт существует в открытом доступе, используется в атаках; CISA SSVC: эксплуатируется; публичный эксплойт по NVD; EPSS 1,0% |

**Почему важно:** Закройте доступ к SharePoint из интернета и обновите RouterOS на подстанциях и в диспетчерских центрах.

Также об этом: [CISA: оповещения и каталог KEV](https://cisa.gov/news-events/alerts/2026/10/01/cisa-adds-one-known-exploited-vulnerability-catalog), [CISA: оповещения и каталог KEV](https://cisa.gov/news-events/alerts/2026/09/27/cisa-adds-two-known-exploited-vulnerabilities-catalog)

### [Уязвимости в IO-Link Master Pepperl+Fuchs позволяют получить root-доступ и атаковать АСУ ТП](https://industrialcyber.co/threats-attacks/nozomi-identifies-19-vulnerabilities-in-pepperlfuchs-io-link-master-enabling-root-access-and-ot-attacks)

*Industrial Cyber · 29.09.2026 · Уязвимость · приоритет: средний (эксплойт: нет) · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

Оригинал: Nozomi identifies 19 vulnerabilities in Pepperl+Fuchs IO-Link Master enabling root access and OT attacks

19 уязвимостей в Pepperl+Fuchs IO-Link Master ICE2-8IOL-K45P-RJ45, включая обход аутентификации и инъекцию команд, позволяют злоумышленнику получить права root и управлять промышленными устройствами.

| Поле | Значение |
| --- | --- |
| Уязвимость | уязвимость в Pepperl+Fuchs IO-Link Master |
| Затронуто | Pepperl+Fuchs IO-Link Master ICE2-8IOL-K45P-RJ45, прошивка EtherNet/IP версии 1.7.3 |
| Обновление | выпущено |
| Временные меры | нет данных |
| Эксплойт | нет |
| Идентификаторы | CVE-2026-27546 |
| CVSS | нет данных |
| CWE | нет данных |
| Последствия | удалённое выполнение кода с правами root, обход аутентификации, модификация конфигураций, манипуляция показаниями датчиков |
| Оборудование | Pepperl+Fuchs IO-Link Master ICE2-8IOL-K45P-RJ45 |
| Протоколы | EtherNet/IP, Modbus TCP, OPC UA, MQTT |
| Сверено по базам | CVE-2026-27546: EPSS 1,0%; CVSS 9.8 по NVD |

**Почему важно:** Закройте доступ к веб-интерфейсу IO-Link Master из интернета и обновите прошивку до исправленной версии.

### [Уязвимость нулевого дня в TDengine позволяет завершить работу OT-серверов](https://darkreading.com/ics-ot-security/one-packet-crash-servers-tdengine)

*Dark Reading · 29.09.2026 · Уязвимость · приоритет: средний (эксплойт: нет данных) · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

Оригинал: One Packet Can Crash OT Servers in Industrial Sectors

Высокоуровневая уязвимость нулевого дня в TDengine позволяет злоумышленнику завершить работу серверов на основе одного пакета.

| Поле | Значение |
| --- | --- |
| Уязвимость | уязвимость нулевого дня в TDengine |
| Затронуто | TDengine |
| Обновление | нет данных |
| Временные меры | Закройте доступ к TDengine из интернета и ограничьте сетевое взаимодействие. |
| Эксплойт | нет данных |
| Идентификаторы | нет данных |
| CVSS | нет данных |
| CWE | нет данных |
| Последствия | Отказ в обслуживании (завершение работы серверов) |

**Почему важно:** Закройте доступ к TDengine из интернета и ограничьте сетевое взаимодействие для промышленных систем.

*Нет в тексте статьи, убрано проверкой: Эксплойт.*

### [Positive Technologies помогла исправить 17 уязвимостей в популярной российской SCADA-системе](https://cnews.ru/news/line/2026-10-01_positive_technologies_pomogla_ispravit)

*CNews · 01.10.2026 · Уязвимость · приоритет: средний (эксплойт: нет данных) · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

Эксперты PT SWARM обнаружили 17 уязвимостей в двух компонентах российской SCADA-системы «Каскад-АСУ».

| Поле | Значение |
| --- | --- |
| Уязвимость | 17 уязвимостей в SCADA-системе «Каскад-АСУ» |
| Затронуто | SCADA-система «Каскад-АСУ» |
| Обновление | нет данных |
| Временные меры | Ограничьте доступ к компонентам SCADA-системы «Каскад-АСУ» для неавторизованных пользователей. |
| Эксплойт | нет данных |
| Идентификаторы | нет данных |
| CVSS | нет данных |
| CWE | нет данных |
| Последствия | нет данных |

**Почему важно:** Закройте доступ к компонентам SCADA-системы «Каскад-АСУ» из интернета и ограничьте доступ к ним для неавторизованных пользователей.

Также об этом: [CNews: Безопасность](https://safe.cnews.ru/news/line/2026-10-01_positive_technologies_pomogla_ispravit)

## 3. ФСТЭК уточнила сроки оценки ИС

ФСТЭК опубликовала разъяснения по порядку и срокам предоставления результатов оценки защищённости информационных систем.

### [ФСТЭК разъяснила порядок и сроки представления результатов оценки защищённости информационных систем](https://1275.ru/compliance/fstek-razyasnila-poryadok-i-sroki-predstavleniya-rezultatov-otsenki-zaschischyonnosti-informatsionnyh-sistem_42689)

*1275.ru: уязвимости и индикаторы · 02.10.2026 · релевантность 0.99 · интерес: Требования регуляторов по ИБ*

ФСТЭК России опубликовала информационное сообщение N 240/92/6722, разъясняющее методику расчета показателя защищенности от базовых угроз на основе приказа N 117 от 11 апреля 2025 года. Результаты расчёта необходимо направлять в соответствующее территориальное управление ФСТЭК не позднее пяти рабочих дней после проведения оценки.

**Почему важно:** Настройте автоматизированный сбор данных о конфигурациях и обновлениях для своевременной отправки отчета в ФСТЭК.

<details><summary>Не вошло в выпуск: 50</summary>

- [Positive Technologies помогла исправить 17 уязвимостей в популярной российской SCADA-системе](https://safe.cnews.ru/news/line/2026-10-01_positive_technologies_pomogla_ispravit) · CNews: Безопасность · оценка 1.00 · повтор уже включённой новости
- [CISA предупреждает о критической RCE-уязвимости в MikroTik RouterOS](https://xakep.ru/2026/10/02/cve-2026-84411) · Хакер · оценка 0.91 · не вошла в лимит выпуска
- [Аттестация и практика работы по приказу ФСТЭК 117](https://habr.com/ru/companies/selectel/articles/1078612) · Хабр: Информационная безопасность · оценка 0.79 · не вошла в лимит выпуска
- [Сентябрьский дайджест трендовых уязвимостей](https://ptsecurity.com/research/analytics/trending-vulnerability-digest-september-2026/) · Positive Technologies: новости · оценка 0.75 · не вошла в лимит выпуска
- [Fortinet предупреждает о критической уязвимости, которая активно используется в 0-day атаках для выполнения несанкционированного кода или команд на уязвимых устройствах](https://t.me/true_secator/8672) · SecAtor · оценка 0.75 · не вошла в лимит выпуска
- [Zero-Day Exploitation of Citrix NetScaler ADC and Gateway: CVE-2026-88771 and CVE-2026-88772](https://rapid7.com/blog/post/etr-zero-day-exploitation-of-citrix-netscaler-adc-and-gateway-cve-2026-88771-and-cve-2026-88772) · Rapid7: блог об угрозах · оценка 0.72 · не вошла в лимит выпуска
- [Netscaler снова под прицелом: вышли исправления для двух 0Day](https://t.me/ZerodayAlert/854) · ZeroDay Alert · оценка 0.72 · повтор уже включённой новости
- [Cisco выпустила обновления для устранения критической 0-day в Catalyst SD-WAN Manager (отслеживаемой как CVE-2026-76504), которую злоумышленники активно используют для повышения…](https://t.me/true_secator/8666) · SecAtor · оценка 0.71 · не вошла в лимит выпуска
- [CISA Adds One Known Exploited Vulnerability to Catalog](https://cisa.gov/news-events/alerts/2026/10/01/cisa-adds-one-known-exploited-vulnerability-catalog) · CISA: оповещения и каталог KEV · оценка 0.71 · повтор уже включённой новости
- [Critical Zero-Day Vulnerabilities Exploited in Citrix NetScaler ADC, Gateway](https://cisa.gov/news-events/alerts/2026/09/27/critical-zero-day-vulnerabilities-exploited-citrix-netscaler-adc-gateway) · CISA: оповещения и каталог KEV · оценка 0.71 · повтор уже включённой новости
- [Продолжаем отслеживать трендовые угрозы и на текущий момент выделим следующие](https://t.me/true_secator/8670) · SecAtor · оценка 0.71 · не вошла в лимит выпуска
- [CISA Adds Two Known Exploited Vulnerabilities to Catalog](https://cisa.gov/news-events/alerts/2026/09/27/cisa-adds-two-known-exploited-vulnerabilities-catalog) · CISA: оповещения и каталог KEV · оценка 0.71 · повтор уже включённой новости
- [Citrix Patches Critical Zero Days Under Active Exploitation](https://infosecurity-magazine.com/news/citrix-patches-critical-zero-days) · Infosecurity Magazine · оценка 0.70 · не вошла в лимит выпуска
- [Fortinet warns of critical FortiMail flaw exploited in zero-day attacks](https://bleepingcomputer.com/news/security/fortinet-warns-of-critical-fortimail-flaw-exploited-in-zero-day-attacks) · BleepingComputer · оценка 0.70 · повтор уже включённой новости
- [В продолжение к предыдущему: в своем отчете Mandiant приводит дополнительные подробности о том, как используется уязвимость CVE-2026-88772, подтверждая некоторые из тех же моделей…](https://t.me/true_secator/8663) · SecAtor · оценка 0.70 · не вошла в лимит выпуска
- [September "In the Trend of VM" (#31): vulnerabilities in TeamCity, TrueConf, SharePoint, Windows, and Zimbra Collaboration](https://t.me/avleonovcom/1690) · Vulnerability Management and more (Леонов) · оценка 0.70 · ниже порога релевантности
- [CISA Adds One Known Exploited Vulnerability to Catalog](https://cisa.gov/news-events/alerts/2026/09/30/cisa-adds-one-known-exploited-vulnerability-catalog) · CISA: оповещения и каталог KEV · оценка 0.70 · ниже порога релевантности
- [ТОП-5 ИБ‑событий недели по версии Jet CSIRT](https://habr.com/ru/companies/jetinfosystems/news/1087924) · Хабр: новости ИБ · оценка 0.70 · ниже порога релевантности
- [Schneider Electric, SECLAB expand OT cybersecurity collaboration for industrial infrastructure](https://industrialcyber.co/news/schneider-electric-seclab-expand-ot-cybersecurity-collaboration-for-industrial-infrastructure) · Industrial Cyber · оценка 0.64 · ниже порога релевантности
- [Alliance for Critical Infrastructure expands membership across US sectors to address evolving cyber, physical threats](https://industrialcyber.co/critical-infrastructure/alliance-for-critical-infrastructure-expands-membership-across-us-sectors-to-address-evolving-cyber-physical-threats) · Industrial Cyber · оценка 0.62 · ниже порога релевантности
- [«Цифровые решения» и Positive Technologies усилили мониторинг кибербезопасности энергетического холдинга](https://habr.com/ru/companies/dsol/news/1087934) · Хабр: новости ИБ · оценка 0.61 · ниже порога релевантности
- [Police Target KillSec Ransomware Group with Arrests and Seizures](https://infosecurity-magazine.com/news/police-target-killsec-ransomware) · Infosecurity Magazine · оценка 0.56 · ниже порога релевантности
- [Обзор кибератак и уязвимостей за прошедшую неделю: 28 сентября - 2 октября 2026 года](https://securitymedia.org/news/obzor-kiberatak-i-uyazvimostey-za-proshedshuyu-nedelyu-28-sentyabrya-2-oktyabrya-2026-goda.html) · SecurityMedia · оценка 0.55 · ниже порога релевантности
- [Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в Citrix NetScaler, связанной с развертыванием веб-оболочек и вредоносного ПО для туннелирования, получением root-доступа…](https://t.me/true_secator/8662) · SecAtor · оценка 0.51 · ниже порога релевантности
- [Обновление БДУ](https://t.me/bdufstecru/3488) · БДУ ФСТЭК России · оценка 0.48 · ниже порога релевантности
- [Каждая вторая уязвимость от ИИ даёт RCE. У обычных находок таких только 26%](https://securitylab.ru/news/578126.php) · SecurityLab.ru · оценка 0.48 · ниже порога релевантности
- [Минцифры опубликовало проект третьего пакета мер противодействия мошенникам](https://comnews.ru/content/247650/2026-10-02/2026-w40/1008/mincifry-opublikovalo-proekt-tretego-paketa-mer-protivodeystviya-moshennikam) · ComNews · оценка 0.48 · ниже порога релевантности
- [Госзакупки российского ПО перекраивают рынок: антивирусных поставщиков стало на 18% меньше](https://securitymedia.org/news/goszakupki-rossiyskogo-po-perekraivayut-rynok-antivirusnykh-postavshchikov-stalo-na-18-menshe.html) · SecurityMedia · оценка 0.48 · ниже порога релевантности
- [Positive Technologies представила сентябрьский дайджест трендовых уязвимостей](https://ptsecurity.com/about/news/pt-has-released-its-sept-digest-of-trending-vulnerabilities) · Positive Technologies: новости · оценка 0.47 · ниже порога релевантности
- [Apple выпустила обновления для устранения 0-day, используемой в «чрезвычайно сложных» таргетированных атаках на устройства iOS](https://t.me/true_secator/8656) · SecAtor · оценка 0.47 · ниже порога релевантности
- [«Айсорс» выбрал SafeTech CA для миграции на российский центр сертификации](https://cnews.ru/news/line/2026-10-01_ajsors_vybral_safetech_ca_dlya) · CNews · оценка 0.47 · ниже порога релевантности
- [Минцифры вынесло Антифрод 3.0 на обсуждение: что предлагают изменить для SIM-карт, сайтов и Госуслуг](https://securitylab.ru/news/578108.php) · SecurityLab.ru · оценка 0.47 · ниже порога релевантности
- [Импортозамещение 2026: от экстренных замен к устойчивой архитектуре — итоги конференции TAdviser](https://tadviser.ru/a/968494) · TAdviser · оценка 0.47 · ниже порога релевантности
- [CISA Adds One Known Exploited Vulnerability to Catalog](https://cisa.gov/news-events/alerts/2026/09/29/cisa-adds-one-known-exploited-vulnerability-catalog) · CISA: оповещения и каталог KEV · оценка 0.47 · ниже порога релевантности
- [CISA Adds One Known Exploited Vulnerability to Catalog](https://cisa.gov/news-events/alerts/2026/09/25/cisa-adds-one-known-exploited-vulnerability-catalog) · CISA: оповещения и каталог KEV · оценка 0.46 · ниже порога релевантности
- [Интернет под замком подорожал вдвое: Роскомнадзор получит почти 60 млрд](https://securitylab.ru/news/578169.php) · SecurityLab.ru · оценка 0.46 · ниже порога релевантности
- [Степан Клепиков оценил для ComNews ситуацию с уязвимостью overpass в российских системах SAP](https://www.securityvision.ru/news/stepan-klepikov-otsenil-dlya-comnews-situatsiyu-s-uyazvimostyu-overpass-v-rossiyskikh-sistemakh-sap/) · SecurityVision.ru · оценка 0.46 · ниже порога релевантности
- [K2 Cloud и «К2 Кибербезопасность» защитили передачу данных между Whoosh и ГИС](https://safe.cnews.ru/news/line/2026-10-01_k2_cloud_i_k2_kiberbezopasnost) · CNews: Безопасность · оценка 0.46 · ниже порога релевантности
- [cKEV Index: успеть до полуночи](https://securitylab.ru/analytics/578238.php) · SecurityLab.ru · оценка 0.46 · ниже порога релевантности
- [ViPNet EDI Soap Gate 3 в реестрах Минпромторга России](https://safe.cnews.ru/news/line/2026-10-01_vipnet_edi_soap_gate_3_v_reestrah_minpromtorga) · CNews: Безопасность · оценка 0.45 · ниже порога релевантности
- [Мониторинг законодательства в области информационных технологий и телекоммуникаций за сентябрь 2026 года](https://cnews.ru/news/line/2026-10-01_monitoring_zakonodatelstva) · CNews · оценка 0.45 · ниже порога релевантности
- [CISA Adds Two Known Exploited Vulnerabilities to Catalog](https://cisa.gov/news-events/alerts/2026/10/02/cisa-adds-two-known-exploited-vulnerabilities-catalog) · CISA: оповещения и каталог KEV · оценка 0.45 · ниже порога релевантности
- [Apple patches CoreGraphics zero-day flaw exploited in attacks](https://bleepingcomputer.com/news/security/apple-patches-coregraphics-zero-day-flaw-exploited-in-attacks) · BleepingComputer · оценка 0.45 · ниже порога релевантности
- [Hackers exploit Citrix NetScaler zero-day to deploy web shells](https://bleepingcomputer.com/news/security/hackers-exploit-citrix-netscaler-zero-day-to-deploy-web-shells) · BleepingComputer · оценка 0.45 · ниже порога релевантности
- [ViPNet EDI Soap Gate 3 в реестрах Минпромторга России](https://cnews.ru/news/line/2026-10-01_vipnet_edi_soap_gate_3_v_reestrah_minpromtorga) · CNews · оценка 0.45 · ниже порога релевантности
- [Defending Against Active Exploitation of Citrix NetScaler ADC and Gateway Appliances](https://cloud.google.com/blog/topics/threat-intelligence/defending-against-active-exploitation-of-citrix-netscaler-adc-and-gateway-appliances) · Google Cloud: Threat Intelligence · оценка 0.45 · ниже порога релевантности
- [Спикател и ГК «Инфобезопасность» объявили об информационном партнёрстве](https://infobezopasnost.ru/blog/news/spikatel-i-gk-infobezopasnost-obyavili-ob-informatsionnom-partnyorstve) · Инфобезопасность · оценка 0.26 · ниже порога релевантности
- [Опубликованы новые результаты тестирования обновлений ПО](https://t.me/bdufstecru/3492) · БДУ ФСТЭК России · оценка 0.24 · ниже порога релевантности
- [В новой Госдуме комитет по технологическому лидерству появился](https://t.me/alukatsky/15354) · Пост Лукацкого · оценка 0.23 · ниже порога релевантности
- [Минцифры выступает за сохранение действующих условий для ИТ-льгот](https://cnews.ru/news/line/2026-10-01_mintsifry_vystupaet_za_sohranenie) · CNews · оценка 0.20 · ниже порога релевантности

</details>

---

## Как составлен выпуск

- Публикаций за период: 1807. Кандидатов после поиска по интересам: 60. В выпуске: 10 из 7 источников.
- Поиск: openai:text-embeddings-v2-doc/latest. Оценка и тексты: openai:qwen3.6-35b-a3b/latest.
- Пересказов одной новости объединено: 3.
- Приоритеты атак и уязвимостей по правилам датасета организаторов: высокий 4, средний 4, низкий 1.
- Проверка записей по тексту статей: исправлено записей 1, убрано полей и фраз 1.
