---
profile: "Специалист по ИБ АСУ ТП (03-stricter)"
profile_version: 1
audience: "specialist"
period_start: "2026-09-25"
period_end: "2026-10-02"
generated: "2026-10-15T05:21+03:00"
llm: "ollama:gpt-oss:120b"
embedding: "ollama:embeddinggemma:300m"
sources: 6
publications: 1716
candidates: 60
entries: 10
manual_minutes: 83
---

# CyberAv3ngers атакуют US водоснабжение через уязвимости PLC

**Профиль:** Специалист по ИБ АСУ ТП (03-stricter) (версия 1)  
**Период:** 25.09.2026 - 02.10.2026  
**Сформирован:** 15.10.2026 05:21 МСК

*Вместо ручной работы: ассистент просмотрел 1 716 публикаций и написал 10 записей за 4 с; вручную это около 83 мин по журналу аналитика ИБ: 1,3 с на публикацию и 4,6 мин на запись.*

## Содержание

- [1. Атаки](#1-атаки)
- [2. Уязвимости](#2-уязвимости)
- [3. Требования ФСТЭК к аттестации ИС](#3-требования-фстэк-к-аттестации-ис)
- [4. Расширение OT-кибербезопасности в промышленности](#4-расширение-ot-кибербезопасности-в-промышленности)

## Главное

- CyberAv3ngers эксплуатируют уязвимости в PLC Unitronics и Rockwell/Allen-Bradley, уже проводят атаки на системы водоснабжения США
- Контроллеры Johnson Controls EasyIO Neo утекли учётные данные через HTTP и отладочные порты – закройте доступ из внешних сетей
- Две уязвимости в CODESYS вызывают отказ в обслуживании и искажение данных мониторинга – обновите прошивки и включите контроль целостности
- ABB PCM600 позволяет повысить привилегии и выполнить Path Traversal – примените патч и ограничьте доступ к файловой системе
- Positive Technologies исправила 17 уязвимостей в российской SCADA-системе – проверьте, установлены ли исправления, и проведите повторный аудит

## 1. Атаки

Низкий приоритет: 1. Порядок по правилу: атаки на ТЭК и промышленность РФ приоритетнее других отраслей РФ, зарубежные инциденты - в конце.

### [Иранская группировка CyberAv3ngers атакует системы водоснабжения США через уязвимости PLC Unitronics и Rockwell/Allen-Bradley](https://t.me/alukatsky/15356)

*Пост Лукацкого · 02.10.2026 · Атака · приоритет: низкий (вне РФ или страна не названа) · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

Оригинал: На KazHackStan я слушал выступление Дениса Ласкова про атаки на критическую инфраструктуру и зацепила меня одна история

Группировка использовала открытые в Интернет контроллеры PLC для удалённого управления насосами и клапанами, вызывая отключения и падение давления в водоснабжении. Атаки привели к масштабным перебоям в работе более 100 объектов в 12 штатах.

| Поле | Значение |
| --- | --- |
| Страна жертвы | США |
| Группировка | CyberAv3ngers |
| Дата атаки | 7 апреля 2026 |
| Отрасли и компании | Водоснабжение, коммунальные услуги |
| Вектор атаки | Экспозиция PLC в Интернет, удалённый доступ к контроллерам |
| Первоначальный доступ | Подключение к публично доступным PLC через интернет |
| Затронутые продукты | Unitronics PLC, Rockwell/Allen-Bradley MicroLogix 1100/1400 |
| Инструменты | нет данных |
| Уязвимости | нет данных |
| Техники ATT&CK | нет данных |
| Индикаторы компрометации | нет |

**Почему важно:** Для инженеров ИБ подстанций: открытые в Интернет PLC могут быть компрометированы без доступа к корпоративной сети, поэтому необходимо изолировать и защищать такие устройства.

## 2. Уязвимости

Средний приоритет: 6. Порядок по правилу: уязвимости с известным эксплойтом показываются первыми.

### [Две уязвимости в CODESYS позволяют вызвать отказ в обслуживании и исказить данные мониторинга](https://1275.ru/vulnerability/dve-uyazvimosti-v-codesys-pozvolyayut-vyzvat-otkaz-v-obsluzhivanii-i-iskazit-dannye-monitoringa_42653)

*1275.ru: уязвимости и индикаторы · касается нас: CODESYS · 02.10.2026 · Уязвимость · приоритет: средний (эксплойт: нет) · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

Две уязвимости в CODESYS позволяют злоумышленнику исчерпать память клиента шлюза (DoS) и искажать данные при одновременных запросах к контроллеру (коррупция данных, отказ).

| Поле | Значение |
| --- | --- |
| Уязвимость | уязвимость в CODESYS |
| Затронуто | CODESYS Development System 3, CODESYS Gateway, Edge Gateway Windows, панель HMI, OPC DA сервер, библиотека PLCHandler, Runtime Toolkit, CODESYS Control для Linux и Linux ARM, Raspberry Pi, Beckhoff CX, PFC100, PFC200, PLCnext, WAGO Touch Panels 600, Virtual Control SL, Safety SIL2; версии до 3.5.22.40 (Linux-платформы ждут 4.23.0.0). |
| Обновление | Для части версий исправление ещё не выпущено. |
| Временные меры | Ограничьте одновременное подключение более одного клиента к контроллеру; отключите внешние шлюзы, если они не нужны; используйте только локальный доступ к среде разработки. |
| Эксплойт | нет |
| Идентификаторы | CVE-2026-76992, CVE-2026-79625 |
| CVSS | нет данных |
| CWE | нет данных |
| Последствия | Отказ в обслуживании (исчерпание памяти), искажение/коррупция данных мониторинга, возможный отказ контроллера. |
| Сверено по базам | CVE-2026-76992: EPSS 0,3%; CVE-2026-79625: EPSS 0,2% |

**Почему важно:** Обновите все компоненты CODESYS до версий 3.5.22.40 или 4.23.0.0; пока патч недоступен, ограничьте одновременный доступ к контроллерам и отключите внешние шлюзы. Для части версий исправление ещё не выпущено.

*Нет в тексте статьи, убрано проверкой: Обновление, CWE.*

### [ABB Protection and Control IED Manager PCM600 – повышение привилегий и Path Traversal](https://cisa.gov/news-events/ics-advisories/icsa-26-274-03)

*CISA ICS Advisories · касается нас: ABB PCM600 · 01.10.2026 · Уязвимость · приоритет: средний (эксплойт: нет данных) · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

Оригинал: ABB Protection and Control IED Manager PCM600

Уязвимости позволяют локальному пользователю с учётными данными повысить привилегии до уровня LocalSystem и записать файлы вне каталога распаковки архива.

| Поле | Значение |
| --- | --- |
| Уязвимость | уязвимость в ABB Protection and Control IED Manager PCM600 |
| Затронуто | ABB Protection and Control IED Manager PCM600 версии ≤2.14 (CVE-2026-15952, CVE-2026-15953) |
| Обновление | нет данных |
| Временные меры | Настройте ABBPCMSchedulerService на запуск под тем же Windows-аккаунтом, что используется для PCM600, и включайте параметр «Always trust IED security certificates» только в доверенной среде. |
| Эксплойт | нет данных |
| Идентификаторы | CVE-2026-15952, CVE-2026-15953 |
| CVSS | 6.4 (CVSS:3.1/AV:L/AC:H/PR:H/UI:N/S:U/C:H/I:H/A:H) |
| Доступ | локально |
| Сложность | высокая |
| Права | высокие |
| Действия пользователя | не нужны |
| CWE | CWE-732 |
| Последствия | Эскалация привилегий до LocalSystem, запись произвольных файлов, потенциальный контроль над системой. |
| Оборудование | ABB Protection and Control IED Manager PCM600 |
| Сверено по базам | CVE-2026-15952: EPSS 0,1%; CVE-2026-15953: EPSS 0,1% |

**Почему важно:** Для инженеров ИБ подстанций: ограничьте запуск ABBPCMSchedulerService от имени отдельного сервисного аккаунта и отключите обработку архивов из ненадёжных источников.

### [Контроллеры Johnson Controls EasyIO Neo допускают утечку учётных данных через HTTP и отладочные порты](https://1275.ru/vulnerability/kontrollery-johnson-controls-easyio-neo-dopuskayut-utechku-uchyotnyh-dannyh-cherez-http-i-otladochnye-porty_42663)

*1275.ru: уязвимости и индикаторы · 02.10.2026 · Уязвимость · приоритет: средний (эксплойт: нет) · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

Уязвимости позволяют перехватить логины, пароли и идентификаторы сессий по HTTP и получить служебные данные через отладочный порт.

| Поле | Значение |
| --- | --- |
| Уязвимость | уязвимость в Johnson Controls EasyIO Neo |
| Затронуто | EasyIO Neo Series EC V3.3b62, EC V3.3b63, CW V3.3b24, CW V3.3b25 |
| Обновление | выпущено, версии EC V3.3b64 и CW V3.3b26 |
| Временные меры | Включите HTTPS/TLS и отключите HTTP; разместите контроллеры в изолированном сегменте сети за межсетевым экраном. |
| Эксплойт | нет |
| Идентификаторы | CVE-2026-64893, CVE-2026-64892 |
| CVSS | 5.4 |
| CWE | нет данных |
| Последствия | Перехват учётных данных, раскрытие служебной информации, возможность дальнейшего доступа к системе управления. |
| Оборудование | Johnson Controls EasyIO Neo Series EC и CW |
| Протоколы | BACnet, Modbus |
| Сверено по базам | CVE-2026-64893: EPSS 0,1%; CVE-2026-64892: EPSS 0,2% |

**Почему важно:** Защитите веб-интерфейсы контроллеров EasyIO Neo, иначе злоумышленник в том же сегменте сети получит учётные данные и служебную информацию, что может привести к компрометации АСУ ТП подстанций и диспетчерских центров.

Также об этом: [CISA ICS Advisories](https://cisa.gov/news-events/ics-advisories/icsa-26-274-04)

### [Positive Technologies помогла исправить 17 уязвимостей в популярной российской SCADA-системе](https://safe.cnews.ru/news/line/2026-10-01_positive_technologies_pomogla_ispravit)

*CNews: Безопасность · 01.10.2026 · Уязвимость · приоритет: средний (эксплойт: нет данных) · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

Уязвимости позволяют перехватить графический интерфейс SCADA и получить доступ к виртуальному контроллеру, что даёт возможность управлять технологическим процессом.

| Поле | Значение |
| --- | --- |
| Уязвимость | уязвимости в SCADA-системе Каскад |
| Затронуто | SCADA «Каскад» версии 8.3; компоненты KWebVision (BDU:2026-01678–BDU:2026-01682) и KLogic (BDU:2026-01676–BDU:2026-01677, BDU:2026-01683–BDU:2026-01692) |
| Обновление | выпущено, версия 8.3.1 (доступно с 14 апреля 2026 г.) |
| Временные меры | ограничить доступ к компонентам SCADA из внешних и корпоративных сетей, применить межсетевые экраны, внедрить решения для мониторинга трафика в технологической сети |
| Эксплойт | нет данных |
| Идентификаторы | BDU:2026-01678, BDU:2026-01679, BDU:2026-01680, BDU:2026-01681, BDU:2026-01682, BDU:2026-01676, BDU:2026-01677, BDU:2026-01683, BDU:2026-01684, BDU:2026-01685, BDU:2026-01686, BDU:2026-01687, BDU:2026-01688, BDU:2026-01689, BDU:2026-01690, BDU:2026-01691, BDU:2026-01692 |
| CVSS | нет данных |
| CWE | нет данных |
| Последствия | удалённый доступ к графическому интерфейсу SCADA и к виртуальному контроллеру, возможность управления технологическим процессом |

**Почему важно:** Закройте сетевой доступ к компонентам KWebVision и KLogic, используйте межсетевые экраны и мониторинг трафика для защиты АСУ ТП подстанций.

Также об этом: [CNews](https://cnews.ru/news/line/2026-10-01_positive_technologies_pomogla_ispravit)

### [Toptech TMS7 и TopHAT – удалённый доступ к данным и выполнение произвольного кода](https://cisa.gov/news-events/ics-advisories/icsa-26-272-02)

*CISA ICS Advisories · 29.09.2026 · Уязвимость · приоритет: средний (эксплойт: нет данных) · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

Оригинал: Toptech TMS7 and TopHAT

Уязвимости позволяют неавторизованному атакующему экспортировать любые таблицы БД и загружать исполняемые PHP-файлы на сервер.

| Поле | Значение |
| --- | --- |
| Уязвимость | уязвимости в Toptech TMS7 и TopHAT |
| Затронуто | Toptech TMS7 7.6.3; Toptech TopHAT 7.6.3 (CVE-2026-71379, CVE-2026-70356, CVE-2026-72510, CVE-2026-63713, CVE-2026-68954, CVE-2026-68068, CVE-2026-72507, CVE-2026-71302, CVE-2026-69662, CVE-2026-71189) |
| Обновление | выпущено, версия 7.8 |
| Временные меры | нет данных |
| Эксплойт | нет данных |
| Идентификаторы | CVE-2026-71379, CVE-2026-70356, CVE-2026-72510, CVE-2026-63713, CVE-2026-68954, CVE-2026-68068, CVE-2026-72507, CVE-2026-71302, CVE-2026-69662, CVE-2026-71189 |
| CVSS | 10 (CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H) |
| Доступ | по сети |
| Сложность | низкая |
| Права | не нужны |
| Действия пользователя | не нужны |
| CWE | CWE-552, CWE-434 |
| Последствия | удалённый экспорт данных, загрузка и исполнение произвольных файлов, полное компрометирование веб-серверов |
| Сверено по базам | CVE-2026-71379: EPSS 0,4%; CVE-2026-70356: EPSS 0,4%; CVE-2026-72510: EPSS 0,3%; CVE-2026-63713: EPSS 0,3%; CVE-2026-68954: EPSS 0,3%; CVE-2026-68068: EPSS 0,3%; CVE-2026-72507: EPSS 0,3%; CVE-2026-71302: EPSS 0,3%; CVE-2026-69662: EPSS 0,2%; CVE-2026-71189: EPSS 0,2% |

**Почему важно:** Обновите TMS7/TopHAT до версии 7.8, иначе система АСУ ТП подстанций может стать точкой доступа к критическим данным и исполнению кода.

### [Pepperl+Fuchs IO-Link Master ICE2-8IOL-K45P-RJ45: обход аутентификации и выполнение команд с правами root](https://industrialcyber.co/threats-attacks/nozomi-identifies-19-vulnerabilities-in-pepperlfuchs-io-link-master-enabling-root-access-and-ot-attacks)

*Industrial Cyber · 29.09.2026 · Уязвимость · приоритет: средний (эксплойт: нет данных) · релевантность 1.00 · интерес: Безопасность АСУ ТП и промышленных систем*

Оригинал: Nozomi identifies 19 vulnerabilities in Pepperl+Fuchs IO-Link Master enabling root access and OT attacks

Уязвимость позволяет удалённому атакующему получить административную сессию без учётных данных и выполнить команды с привилегиями root, изменяя конфигурацию IO-Link портов и управляя подключёнными датчиками/актуаторами.

| Поле | Значение |
| --- | --- |
| Уязвимость | уязвимость в Pepperl+Fuchs IO-Link Master |
| Затронуто | Pepperl+Fuchs IO-Link Master ICE2-8IOL-K45P-RJ45, EtherNet/IP firmware 1.7.3 |
| Обновление | выпущено, версия исправления не указана в публикации |
| Временные меры | Отключите доступ к HTTPS-интерфейсу из внешних сетей, используйте VLAN/файрвол для ограничения доступа только из доверенных подсетей, измените начальный пароль после установки. |
| Эксплойт | нет данных |
| Идентификаторы | CVE-2026-27546 |
| CVSS | нет данных |
| CWE | нет данных |
| Последствия | Удалённое выполнение команд с правами root, изменение конфигурации, подмена показаний датчиков, управление актуаторами, возможность перехода к другим OT-системам. |
| Оборудование | Pepperl+Fuchs IO-Link Master ICE2-8IOL-K45P-RJ45 |
| Протоколы | EtherNet/IP, Modbus TCP, OPC UA, MQTT |
| Сверено по базам | CVE-2026-27546: EPSS 1,0% |

**Почему важно:** Для инженеров по ИБ подстанций: закрыть доступ к веб-интерфейсу устройства из незашищённых сетей и ограничить привилегии учётных записей.

## 3. Требования ФСТЭК к аттестации ИС

ФСТЭК уточнила порядок и сроки подачи результатов оценки защищённости информационных систем и описала практику проведения аттестации по приказу 117.

### [ФСТЭК разъяснила порядок и сроки представления результатов оценки защищённости информационных систем](https://1275.ru/compliance/fstek-razyasnila-poryadok-i-sroki-predstavleniya-rezultatov-otsenki-zaschischyonnosti-informatsionnyh-sistem_42689)

*1275.ru: уязвимости и индикаторы · 02.10.2026 · релевантность 1.00 · интерес: Требования регуляторов по ИБ*

ФСТЭК России опубликовала информационное сообщение N 240/92/6722, в котором указано, что операторы и обладатели информации государственных ИС обязаны рассчитывать показатель защищённости и направлять результаты в службу не позднее пяти рабочих дней после расчёта. Требования распространяются на все информационные системы, подлежащие защите по нормативным правовым актам России, включая объекты КИИ.

**Почему важно:** Для инженера по ИБ подстанций – внедрите процесс расчёта показателя и обеспечьте передачу отчётов в установленный региональный центр в течение пяти рабочих дней после расчёта.

### [Аттестация и практика работы по приказу ФСТЭК 117](https://habr.com/ru/companies/selectel/articles/1078612)

*Хабр: Информационная безопасность · 28.09.2026 · релевантность 1.00 · интерес: Требования регуляторов по ИБ*

В статье описаны изменения в нормативных актах ФСТЭК, влияющие на процесс аттестации государственных информационных систем, и указано, что компании должны учитывать новые требования приказа № 117 при подготовке к аттестации. Это касается инженеров по ИБ, отвечающих за защиту АСУ ТП подстанций и диспетчерских центров.

**Почему важно:** Подготовьте и актуализируйте документы и процедуры аттестации в соответствии с приказом ФСТЭК № 117 для обеспечения соответствия регуляторным требованиям.

## 4. Расширение OT-кибербезопасности в промышленности

Schneider Electric и SECLAB усиливают сотрудничество, объединяя исследования и разработки для защиты операционных технологий в промышленной инфраструктуре.

### [Schneider Electric и SECLAB расширяют сотрудничество в области кибербезопасности OT для промышленной инфраструктуры](https://industrialcyber.co/news/schneider-electric-seclab-expand-ot-cybersecurity-collaboration-for-industrial-infrastructure)

*Industrial Cyber · касается нас: Schneider Electric · 29.09.2026 · релевантность 0.97 · интерес: Безопасность АСУ ТП и промышленных систем*

Оригинал: Schneider Electric, SECLAB expand OT cybersecurity collaboration for industrial infrastructure

Schneider Electric и SECLAB объявили о расширении совместной работы по внедрению аппаратных решений, обеспечивающих фильтрацию промышленных протоколов на уровне приложений между PLC, DCS и SIS. Решение предназначено для защиты критических коммуникаций в системах автоматизации и может быть интегрировано в существующие архитектуры Schneider Electric.

**Почему важно:** Разверните предложенный SECLAB-аппаратный фильтр протоколов в линию связи PLC/DCS/SIS для усиления защиты АСУ ТП и снижения риска эксплуатации уязвимостей в промышленном оборудовании.

<details><summary>Не вошло в выпуск: 50</summary>

- [Positive Technologies помогла исправить 17 уязвимостей в популярной российской SCADA-системе](https://cnews.ru/news/line/2026-10-01_positive_technologies_pomogla_ispravit) · CNews · оценка 1.00 · повтор уже включённой новости
- [Johnson Controls EasyIO Neo Series EC and CW Controllers](https://cisa.gov/news-events/ics-advisories/icsa-26-274-04) · CISA ICS Advisories · оценка 1.00 · повтор уже включённой новости
- [One Packet Can Crash OT Servers in Industrial Sectors](https://darkreading.com/ics-ot-security/one-packet-crash-servers-tdengine) · Dark Reading · оценка 0.96 · не вошла в лимит выпуска
- [How decades of disconnected modernization created OT security debt manufacturers can’t escape](https://industrialcyber.co/features/how-decades-of-disconnected-modernization-created-ot-security-debt-manufacturers-cant-escape) · Industrial Cyber · оценка 0.92 · не вошла в лимит выпуска
- [Lantronix G520 Series Cellular Gateway](https://cisa.gov/news-events/ics-advisories/icsa-26-272-01) · CISA ICS Advisories · оценка 0.91 · не вошла в лимит выпуска
- [Обновление БДУ](https://t.me/bdufstecru/3488) · БДУ ФСТЭК России · оценка 0.76 · не вошла в лимит выпуска
- [Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в Citrix NetScaler, связанной с развертыванием веб-оболочек и вредоносного ПО для туннелирования, получением root-доступа…](https://t.me/true_secator/8662) · SecAtor · оценка 0.75 · не вошла в лимит выпуска
- [Сентябрьский дайджест трендовых уязвимостей](https://ptsecurity.com/research/analytics/trending-vulnerability-digest-september-2026/) · Positive Technologies: новости · оценка 0.75 · не вошла в лимит выпуска
- [Positive Technologies представила сентябрьский дайджест трендовых уязвимостей](https://ptsecurity.com/about/news/pt-has-released-its-sept-digest-of-trending-vulnerabilities) · Positive Technologies: новости · оценка 0.73 · повтор уже включённой новости
- [Cisco выпустила обновления для устранения критической 0-day в Catalyst SD-WAN Manager (отслеживаемой как CVE-2026-76504), которую злоумышленники активно используют для повышения…](https://t.me/true_secator/8666) · SecAtor · оценка 0.73 · не вошла в лимит выпуска
- [Netscaler снова под прицелом: вышли исправления для двух 0Day](https://t.me/ZerodayAlert/854) · ZeroDay Alert · оценка 0.72 · повтор уже включённой новости
- [Cisco warns of new SD-WAN zero-day exploited in attacks](https://bleepingcomputer.com/news/security/cisco-warns-of-new-sd-wan-authentication-bypass-zero-day-exploited-in-attacks) · BleepingComputer · оценка 0.72 · повтор уже включённой новости
- [Hackers exploit Citrix NetScaler zero-day to deploy web shells](https://bleepingcomputer.com/news/security/hackers-exploit-citrix-netscaler-zero-day-to-deploy-web-shells) · BleepingComputer · оценка 0.72 · повтор уже включённой новости
- [Warning: Two Unpatched Citrix NetScaler RCE Zero-Days Under Active Exploitation](https://thehackernews.com/2026/09/warning-two-unpatched-citrix-netscaler.html) · The Hacker News · оценка 0.71 · не вошла в лимит выпуска
- [Fortinet warns of critical FortiMail flaw exploited in zero-day attacks](https://bleepingcomputer.com/news/security/fortinet-warns-of-critical-fortimail-flaw-exploited-in-zero-day-attacks) · BleepingComputer · оценка 0.71 · не вошла в лимит выпуска
- [Что происходит с продуктом, когда разработчик решает пройти сертификацию ФСТЭК](https://habr.com/ru/companies/multifactor/articles/1088414) · Хабр: Информационная безопасность · оценка 0.71 · не вошла в лимит выпуска
- [Критическая уязвимость обхода аутентификации в WSO2 API Manager (CVE-2026-5430)](https://t.me/cyberok_news/260) · CyberOK · оценка 0.70 · не вошла в лимит выпуска
- [CISA добавила в каталог активно эксплуатируемых уязвимостей обход пути в Fortinet FortiMail](https://1275.ru/vulnerability/cisa-dobavila-v-katalog-aktivno-ekspluatiruemyh-uyazvimostey-obhod-puti-v-fortinet-fortimail_42640) · 1275.ru: уязвимости и индикаторы · оценка 0.70 · повтор уже включённой новости
- [Как приоритизировать новости об уязвимостях вместо балла CVSS](https://habr.com/ru/articles/1086358) · Хабр: Системное администрирование · оценка 0.70 · не вошла в лимит выпуска
- [Более сотни уязвимостей в четырёх продуктах Kiteworks открывают путь к захвату учётных записей и выполнению кода](https://1275.ru/vulnerability/bolee-sotni-uyazvimostey-v-chetyryoh-produktah-kiteworks-otkryvayut-put-k-zahvatu-uchyotnyh-zapisey-i-vypolneniyu-koda_42644) · 1275.ru: уязвимости и индикаторы · оценка 0.70 · не вошла в лимит выпуска
- [ViPNet EDI Soap Gate 3 в реестрах Минпромторга России](https://safe.cnews.ru/news/line/2026-10-01_vipnet_edi_soap_gate_3_v_reestrah_minpromtorga) · CNews: Безопасность · оценка 0.70 · не вошла в лимит выпуска
- [Vulnerability Discovery and Exploitation Trends in the AI Era](https://cloud.google.com/blog/topics/threat-intelligence/vulnerability-discovery-and-exploitation-trends-in-the-ai-era) · Google Cloud: Threat Intelligence · оценка 0.70 · ниже порога релевантности
- [Ирония судьбы](https://t.me/alukatsky/15355) · Пост Лукацкого · оценка 0.70 · ниже порога релевантности
- [Cisco Patches Exploited Catalyst SD-WAN Zero-Day Vulnerability](https://securityweek.com/cisco-patches-exploited-catalyst-sd-wan-zero-day-vulnerability) · SecurityWeek · оценка 0.70 · ниже порога релевантности
- [«Цифровые решения» и Positive Technologies усилили мониторинг кибербезопасности энергетического холдинга](https://habr.com/ru/companies/dsol/news/1087934) · Хабр: новости ИБ · оценка 0.60 · ниже порога релевантности
- [Alliance for Critical Infrastructure expands membership across US sectors to address evolving cyber, physical threats](https://industrialcyber.co/critical-infrastructure/alliance-for-critical-infrastructure-expands-membership-across-us-sectors-to-address-evolving-cyber-physical-threats) · Industrial Cyber · оценка 0.57 · ниже порога релевантности
- [August 2026 Threat Trend Report on APT Attacks (South Korea)](https://asec.ahnlab.com/en/95649) · AhnLab ASEC · оценка 0.55 · ниже порога релевантности
- [Спуфинг кампания CaptiveCrunch: отпуск с «трояном в кармане» или как отельный Wi‑Fi может стать точкой кражи данных](https://habr.com/ru/articles/1087460) · Хабр: Информационная безопасность · оценка 0.55 · ниже порога релевантности
- [Госзакупки российского ПО перекраивают рынок: антивирусных поставщиков стало на 18% меньше](https://securitymedia.org/news/goszakupki-rossiyskogo-po-perekraivayut-rynok-antivirusnykh-postavshchikov-stalo-na-18-menshe.html) · SecurityMedia · оценка 0.53 · ниже порога релевантности
- [Fortinet предупреждает о критической уязвимости, которая активно используется в 0-day атаках для выполнения несанкционированного кода или команд на уязвимых устройствах](https://t.me/true_secator/8672) · SecAtor · оценка 0.49 · ниже порога релевантности
- [D-Link «расследует» информацию о двух критических уязвимостях в роутерах](https://safe.cnews.ru/news/top/2026-09-28_d-link_rassleduet_informatsiyu) · CNews: Безопасность · оценка 0.49 · ниже порога релевантности
- [Продолжаем отслеживать трендовые угрозы и на текущий момент выделим следующие](https://t.me/true_secator/8670) · SecAtor · оценка 0.48 · ниже порога релевантности
- [Импортозамещение 2026: от экстренных замен к устойчивой архитектуре — итоги конференции TAdviser](https://tadviser.ru/a/968494) · TAdviser · оценка 0.48 · ниже порога релевантности
- [Meari IoT Cloud Platform OpenAPI Service](https://cisa.gov/news-events/ics-advisories/icsa-26-274-06) · CISA ICS Advisories · оценка 0.47 · ниже порога релевантности
- [Apple patches CoreGraphics zero-day flaw exploited in attacks](https://bleepingcomputer.com/news/security/apple-patches-coregraphics-zero-day-flaw-exploited-in-attacks) · BleepingComputer · оценка 0.47 · ниже порога релевантности
- [Defending Against Active Exploitation of Citrix NetScaler ADC and Gateway Appliances](https://cloud.google.com/blog/topics/threat-intelligence/defending-against-active-exploitation-of-citrix-netscaler-adc-and-gateway-appliances) · Google Cloud: Threat Intelligence · оценка 0.47 · ниже порога релевантности
- [Custom malware used in Citrix 0-day attacks targeting govt, banks, professional services](https://theregister.com/security/2026/09/29/custom-malware-used-in-citrix-0-day-attacks-targeting-govt-banks-professional-services/5299867) · The Register: Security · оценка 0.46 · ниже порога релевантности
- [Власти проверят российские заводы на тайную подмену плат китайскими](https://cnews.ru/news/top/2026-09-28_elektroniku_budut_proveryat) · CNews · оценка 0.46 · ниже порога релевантности
- [Минцифры представило третий пакет мер по борьбе с кибермошенничеством](https://habr.com/ru/news/1088634) · Хабр: новости ИБ · оценка 0.46 · ниже порога релевантности
- [Три магнитофона, три кинокамеры: сколько у вас на самом деле иностранного ПО](https://habr.com/ru/companies/simpleone/articles/1087848) · Хабр: Информационная безопасность · оценка 0.46 · ниже порога релевантности
- [Спикател и ГК «Инфобезопасность» объявили об информационном партнёрстве](https://infobezopasnost.ru/blog/news/spikatel-i-gk-infobezopasnost-obyavili-ob-informatsionnom-partnyorstve) · Инфобезопасность · оценка 0.30 · ниже порога релевантности
- [«Лаборатория Касперского» присвоила Т1 Интеграция партнёрский статус по технической специализации KICS](https://www.kaspersky.ru/about/press-releases/laboratoriya-kasperskogo-prisvoila-t1-integraciya-partnyorskij-status-po-tehnicheskoj-specializacii-kics) · Лаборатория Касперского: пресс-релизы · оценка 0.29 · ниже порога релевантности
- [Минцифры вынесло Антифрод 3.0 на обсуждение: что предлагают изменить для SIM-карт, сайтов и Госуслуг](https://securitylab.ru/news/578108.php) · SecurityLab.ru · оценка 0.24 · ниже порога релевантности
- [Российским БПЛА облегчат жизнь. Власти снизят требования к локализации батарей](https://cnews.ru/news/top/2026-10-01_batarei_dlya_bpla_vydelyat) · CNews · оценка 0.24 · ниже порога релевантности
- [ОБЭП (ОЭБ) на пороге IT‑компании: как защитить исходный код, сервера и блокчейн‑решения при обследовании и обыске](https://habr.com/ru/articles/1088850) · Хабр: Информационная безопасность · оценка 0.23 · ниже порога релевантности
- [Apple выпустила обновления для устранения 0-day, используемой в «чрезвычайно сложных» таргетированных атаках на устройства iOS](https://t.me/true_secator/8656) · SecAtor · оценка 0.23 · ниже порога релевантности
- [Опубликованы новые результаты тестирования обновлений ПО](https://t.me/bdufstecru/3492) · БДУ ФСТЭК России · оценка 0.23 · ниже порога релевантности
- [Кибербезопасность нового времени: что обсудят на KDW 2026](https://securitylab.ru/news/578191.php) · SecurityLab.ru · оценка 0.22 · ниже порога релевантности
- [Получен сертификат ФСТЭК России на средство многофакторной аутентификации MFA JaCarta-3](https://cnews.ru/news/line/2026-09-29_poluchen_sertifikat_fstek) · CNews · оценка 0.22 · ниже порога релевантности
- [Тренд на ИИ и комплексную защиту: как меняется ситуация на рынке госзакупок ИТ в России](https://cnews.ru/news/line/2026-10-01_trend_na_ii_i_kompleksnuyu) · CNews · оценка 0.21 · ниже порога релевантности

</details>

---

## Как составлен выпуск

- Публикаций за период: 1716. Кандидатов после поиска по интересам: 60. В выпуске: 10 из 6 источников.
- Поиск: ollama:embeddinggemma:300m. Оценка и тексты: ollama:gpt-oss:120b.
- Пересказов одной новости объединено: 2.
- Приоритеты атак и уязвимостей по правилам датасета организаторов: высокий 0, средний 6, низкий 1.
- Проверка записей по тексту статей: исправлено записей 1, убрано полей и фраз 2.
