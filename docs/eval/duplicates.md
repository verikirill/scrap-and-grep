# Склейка дублей: снимок и примеры выпусков

Снимок `data/samples/articles.jsonl`: 2109 публикаций, пары не дальше 3 дней друг от друга. Эмбеддер - хеширующий, порог 0.72.

- Старые правила (хеш, заголовок, близость векторов): 161 пар.
- Правило по номерам CVE и БДУ добавляет: 205 пар.

## Записи примеров, которые правило по номерам склеило бы

| Выпуск | Записей | Склеилось бы | Пары |
|---|---|---|---|
| `digital-transformation-director.md` | 15 | 0 | - |
| `ics-security-engineer.md` | 20 | 1 | Fortinet warns of critical FortiMail flaw exploited in zero- (bleepingcomputer) + CISA добавила в каталог активно эксплуатируемых уязвимостей  (1275) |
| `it-infrastructure-lead.md` | 20 | 0 | - |
| `management-cybersecurity.md` | 15 | 0 | - |
| `management-monthly.md` | 15 | 0 | - |
| `management-weekly.md` | 15 | 0 | - |
| `specialist-daily.md` | 20 | 1 | Более сотни уязвимостей в четырёх продуктах Kiteworks открыв (1275) + Kiteworks EPG получил 10 из 10 по CVSS: удалённая атака прив (tg-zerodayalert) |
| `specialist-weekly.md` | 20 | 0 | - |

## Пары снимка, которые склеивает только правило по номерам

| Общие номера | Первая | Вторая |
|---|---|---|
| CVE-2026-5430 | Уязвимость платформы для интеграции интерфейсов прикладного программирования, приложений и (bdu-incident) | WSO2 and Adobe Commerce Flaws Exploited in Attacks, Added to CISA KEV (thehackernews) |
| CVE-2026-65330 | Эксперты Positive Technologies помогли Google и Apple устранить 11 уязвимостей (pt-news) | Мы помогли Apple устранить уязвимость в ядре ее операционных систем (tg-ptescalator) |
| CVE-2026-35273 | ShinyHunters Renewed Mass Exploitation Campaign Targeting Oracle PeopleSoft (google-ti) | Attackers Bypass WAFs to Exploit Oracle PeopleSoft Flaw and Deploy Web Shells (thehackernews) |
| CVE-2026-65660 | SharePoint RCE and MikroTik RouterOS Flaws Actively Exploited in the Wild (thehackernews) | Уязвимость функции ToolPane.GetPartPreviewAndPropertiesFromMarkup() пакетов программ Micro (bdu-incident) |
| CVE-2026-87902 | Уязвимость функции get_page_template() ядра системы управления содержимым сайта WordPress, (bdu-incident) | 28th September – Threat Intelligence Report (checkpoint-research) |
| CVE-2026-88771 | Certainties in life: Death, taxes, and critical Citrix vulns under attack (theregister-security) | CISA Says Attackers Are Exploiting Two Critical Citrix NetScaler Flaws Globally (thehackernews) |
| CVE-2026-88771 | Certainties in life: Death, taxes, and critical Citrix vulns under attack (theregister-security) | Netscaler снова под прицелом: вышли исправления для двух 0Day (tg-zerodayalert) |
| CVE-2026-88771, CVE-2026-88772 | Certainties in life: Death, taxes, and critical Citrix vulns under attack (theregister-security) | Defending Against Active Exploitation of Citrix NetScaler ADC and Gateway Appliances (google-ti) |
| CVE-2026-88771, CVE-2026-88772 | Certainties in life: Death, taxes, and critical Citrix vulns under attack (theregister-security) | Custom malware used in Citrix 0-day attacks targeting govt, banks, professional services (theregister-security) |
| CVE-2026-88771, CVE-2026-88772 | Certainties in life: Death, taxes, and critical Citrix vulns under attack (theregister-security) | Hackers exploit Citrix NetScaler zero-day to deploy web shells (bleepingcomputer) |
| CVE-2026-88771 | Certainties in life: Death, taxes, and critical Citrix vulns under attack (theregister-security) | Уязвимость контроллера доставки приложений NetScaler ADC (ранее Citrix ADC) и системы конт (bdu-danger) |
| CVE-2026-88772 | Certainties in life: Death, taxes, and critical Citrix vulns under attack (theregister-security) | Уязвимость контроллера доставки приложений NetScaler ADC (ранее Citrix ADC) и системы конт (bdu-incident) |
| CVE-2026-88772 | Certainties in life: Death, taxes, and critical Citrix vulns under attack (theregister-security) | Citrix NetScaler CVE-2026-88772 Exploit Details Show Pre-Auth Path to Shellcode Execution (thehackernews) |
| CVE-2026-88771, CVE-2026-88772 | Certainties in life: Death, taxes, and critical Citrix vulns under attack (theregister-security) | Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в Citrix NetScaler, связанной с р (tg-true-secator) |
| CVE-2026-88772 | Certainties in life: Death, taxes, and critical Citrix vulns under attack (theregister-security) | В продолжение к предыдущему: в своем отчете Mandiant приводит дополнительные подробности о (tg-true-secator) |
| CVE-2026-88771, CVE-2026-88772 | Certainties in life: Death, taxes, and critical Citrix vulns under attack (theregister-security) | Government, Finance Orgs Targeted in Weeks-Long NetScaler Zero-Day Attacks (securityweek) |
| CVE-2026-88771 | CISA Says Attackers Are Exploiting Two Critical Citrix NetScaler Flaws Globally (thehackernews) | Netscaler снова под прицелом: вышли исправления для двух 0Day (tg-zerodayalert) |
| CVE-2026-88771 | CISA Says Attackers Are Exploiting Two Critical Citrix NetScaler Flaws Globally (thehackernews) | Defending Against Active Exploitation of Citrix NetScaler ADC and Gateway Appliances (google-ti) |
| CVE-2026-88771 | CISA Says Attackers Are Exploiting Two Critical Citrix NetScaler Flaws Globally (thehackernews) | Custom malware used in Citrix 0-day attacks targeting govt, banks, professional services (theregister-security) |
| CVE-2026-88771 | CISA Says Attackers Are Exploiting Two Critical Citrix NetScaler Flaws Globally (thehackernews) | Hackers exploit Citrix NetScaler zero-day to deploy web shells (bleepingcomputer) |
| CVE-2026-88771 | CISA Says Attackers Are Exploiting Two Critical Citrix NetScaler Flaws Globally (thehackernews) | Уязвимость контроллера доставки приложений NetScaler ADC (ранее Citrix ADC) и системы конт (bdu-danger) |
| CVE-2026-88771 | CISA Says Attackers Are Exploiting Two Critical Citrix NetScaler Flaws Globally (thehackernews) | Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в Citrix NetScaler, связанной с р (tg-true-secator) |
| CVE-2026-88771 | CISA Says Attackers Are Exploiting Two Critical Citrix NetScaler Flaws Globally (thehackernews) | Government, Finance Orgs Targeted in Weeks-Long NetScaler Zero-Day Attacks (securityweek) |
| CVE-2026-67276, CVE-2026-86060 | Санкционные роутеры угрожают безопасности россиян. Операторов обязали проверить каждый – р (cnews-safe) | CISA warns of critical pre-auth RCE flaw in MikroTik RouterOS (bleepingcomputer) |
| CVE-2026-86510 | D-Link «расследует» информацию о двух критических уязвимостях в роутерах (cnews-safe) | Уязвимость функции tunnel_set_params() компонента L2TP Control Message Parser микропрограм (bdu-danger) |
| CVE-2026-86950 | Apple Patches CoreGraphics Flaw Possibly Exploited in Targeted Attacks (thehackernews) | Apple Emergency Patch for iOS 26, macOS26, macOS15 (CVE-2026-86950), (Mon, Sep 28th) (sans-isc) |
| CVE-2026-86950 | Apple Patches CoreGraphics Flaw Possibly Exploited in Targeted Attacks (thehackernews) | Apple patches CoreGraphics zero-day already exploited in targeted attacks (theregister-security) |
| CVE-2026-86950 | Apple Patches CoreGraphics Flaw Possibly Exploited in Targeted Attacks (thehackernews) | Внеплановое обновление iOS 26.7.1: что исправила Apple (tg-zerodayalert) |
| CVE-2026-86950 | Apple Patches CoreGraphics Flaw Possibly Exploited in Targeted Attacks (thehackernews) | Apple Zero-Day Vulnerability Weaponized in Targeted Attacks (darkreading) |
| CVE-2026-86950 | Apple Patches CoreGraphics Flaw Possibly Exploited in Targeted Attacks (thehackernews) | Apple CoreGraphics PoC Emerges as WhatsApp PDF Checks Hint at Possible Delivery Path (thehackernews) |
| CVE-2026-86950 | Apple Patches CoreGraphics Flaw Possibly Exploited in Targeted Attacks (thehackernews) | Apple исправила использовавшуюся в атаках 0-day-уязвимость в CoreGraphics (xakep) |
| CVE-2026-86950 | Apple Emergency Patch for iOS 26, macOS26, macOS15 (CVE-2026-86950), (Mon, Sep 28th) (sans-isc) | Apple patches CoreGraphics zero-day flaw exploited in attacks (bleepingcomputer) |
| CVE-2026-86950 | Apple Emergency Patch for iOS 26, macOS26, macOS15 (CVE-2026-86950), (Mon, Sep 28th) (sans-isc) | Apple patches CoreGraphics zero-day already exploited in targeted attacks (theregister-security) |
| CVE-2026-86950 | Apple Emergency Patch for iOS 26, macOS26, macOS15 (CVE-2026-86950), (Mon, Sep 28th) (sans-isc) | Внеплановое обновление iOS 26.7.1: что исправила Apple (tg-zerodayalert) |
| CVE-2026-86950 | Apple Emergency Patch for iOS 26, macOS26, macOS15 (CVE-2026-86950), (Mon, Sep 28th) (sans-isc) | Apple Zero-Day Vulnerability Weaponized in Targeted Attacks (darkreading) |
| CVE-2026-86950 | Apple Emergency Patch for iOS 26, macOS26, macOS15 (CVE-2026-86950), (Mon, Sep 28th) (sans-isc) | Apple CoreGraphics PoC Emerges as WhatsApp PDF Checks Hint at Possible Delivery Path (thehackernews) |
| CVE-2026-86950 | Apple Emergency Patch for iOS 26, macOS26, macOS15 (CVE-2026-86950), (Mon, Sep 28th) (sans-isc) | Apple исправила использовавшуюся в атаках 0-day-уязвимость в CoreGraphics (xakep) |
| CVE-2026-86950 | Apple Emergency Patch for iOS 26, macOS26, macOS15 (CVE-2026-86950), (Mon, Sep 28th) (sans-isc) | Уязвимость системного фреймворка Apple CoreGraphics операционных систем iOS, MacOS и iPadO (bdu-incident) |
| CVE-2026-86950 | Apple patches CoreGraphics zero-day flaw exploited in attacks (bleepingcomputer) | Внеплановое обновление iOS 26.7.1: что исправила Apple (tg-zerodayalert) |
| CVE-2026-86950 | Apple patches CoreGraphics zero-day flaw exploited in attacks (bleepingcomputer) | Apple Zero-Day Vulnerability Weaponized in Targeted Attacks (darkreading) |
| CVE-2026-86950 | Apple patches CoreGraphics zero-day flaw exploited in attacks (bleepingcomputer) | Apple CoreGraphics PoC Emerges as WhatsApp PDF Checks Hint at Possible Delivery Path (thehackernews) |
| CVE-2026-86950 | Apple patches CoreGraphics zero-day flaw exploited in attacks (bleepingcomputer) | Apple исправила использовавшуюся в атаках 0-day-уязвимость в CoreGraphics (xakep) |
| CVE-2026-86950 | Apple patches CoreGraphics zero-day flaw exploited in attacks (bleepingcomputer) | Уязвимость системного фреймворка Apple CoreGraphics операционных систем iOS, MacOS и iPadO (bdu-incident) |
| CVE-2026-84411 | MikroTik RouterOS (cisa-ics) | CISA warns of critical pre-auth RCE flaw in MikroTik RouterOS (bleepingcomputer) |
| CVE-2026-84411 | MikroTik RouterOS (cisa-ics) | MikroTik's RouterOS has a near maximum severity bug: CISA urges updating ASAP (cybernews) |
| CVE-2026-84411 | MikroTik RouterOS (cisa-ics) | CISA предупреждает о критической RCE-уязвимости в MikroTik RouterOS (xakep) |
| CVE-2026-88771 | Netscaler снова под прицелом: вышли исправления для двух 0Day (tg-zerodayalert) | Defending Against Active Exploitation of Citrix NetScaler ADC and Gateway Appliances (google-ti) |
| CVE-2026-88771 | Netscaler снова под прицелом: вышли исправления для двух 0Day (tg-zerodayalert) | Custom malware used in Citrix 0-day attacks targeting govt, banks, professional services (theregister-security) |
| CVE-2026-88771 | Netscaler снова под прицелом: вышли исправления для двух 0Day (tg-zerodayalert) | Hackers exploit Citrix NetScaler zero-day to deploy web shells (bleepingcomputer) |
| CVE-2026-88771 | Netscaler снова под прицелом: вышли исправления для двух 0Day (tg-zerodayalert) | Уязвимость контроллера доставки приложений NetScaler ADC (ранее Citrix ADC) и системы конт (bdu-danger) |
| CVE-2026-88771 | Netscaler снова под прицелом: вышли исправления для двух 0Day (tg-zerodayalert) | Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в Citrix NetScaler, связанной с р (tg-true-secator) |
| CVE-2026-88771 | Netscaler снова под прицелом: вышли исправления для двух 0Day (tg-zerodayalert) | Government, Finance Orgs Targeted in Weeks-Long NetScaler Zero-Day Attacks (securityweek) |
| CVE-2026-88771 | Netscaler снова под прицелом: вышли исправления для двух 0Day (tg-zerodayalert) | Citrix NetScaler прячет веб-шелл за CSS и оставляет superuser после взлома (tg-zerodayalert) |
| CVE-2026-88771, CVE-2026-88772 | Defending Against Active Exploitation of Citrix NetScaler ADC and Gateway Appliances (google-ti) | Custom malware used in Citrix 0-day attacks targeting govt, banks, professional services (theregister-security) |
| CVE-2026-88771, CVE-2026-88772 | Defending Against Active Exploitation of Citrix NetScaler ADC and Gateway Appliances (google-ti) | Hackers exploit Citrix NetScaler zero-day to deploy web shells (bleepingcomputer) |
| CVE-2026-88771 | Defending Against Active Exploitation of Citrix NetScaler ADC and Gateway Appliances (google-ti) | Уязвимость контроллера доставки приложений NetScaler ADC (ранее Citrix ADC) и системы конт (bdu-danger) |
| CVE-2026-88772 | Defending Against Active Exploitation of Citrix NetScaler ADC and Gateway Appliances (google-ti) | Уязвимость контроллера доставки приложений NetScaler ADC (ранее Citrix ADC) и системы конт (bdu-incident) |
| CVE-2026-88772 | Defending Against Active Exploitation of Citrix NetScaler ADC and Gateway Appliances (google-ti) | Citrix NetScaler CVE-2026-88772 Exploit Details Show Pre-Auth Path to Shellcode Execution (thehackernews) |
| CVE-2026-88771, CVE-2026-88772 | Defending Against Active Exploitation of Citrix NetScaler ADC and Gateway Appliances (google-ti) | Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в Citrix NetScaler, связанной с р (tg-true-secator) |
| CVE-2026-88772 | Defending Against Active Exploitation of Citrix NetScaler ADC and Gateway Appliances (google-ti) | В продолжение к предыдущему: в своем отчете Mandiant приводит дополнительные подробности о (tg-true-secator) |
| CVE-2026-88771, CVE-2026-88772 | Defending Against Active Exploitation of Citrix NetScaler ADC and Gateway Appliances (google-ti) | Government, Finance Orgs Targeted in Weeks-Long NetScaler Zero-Day Attacks (securityweek) |
| CVE-2026-88771 | Defending Against Active Exploitation of Citrix NetScaler ADC and Gateway Appliances (google-ti) | Citrix NetScaler прячет веб-шелл за CSS и оставляет superuser после взлома (tg-zerodayalert) |
| CVE-2026-86950 | Apple patches CoreGraphics zero-day already exploited in targeted attacks (theregister-security) | Внеплановое обновление iOS 26.7.1: что исправила Apple (tg-zerodayalert) |
| CVE-2026-86950 | Apple patches CoreGraphics zero-day already exploited in targeted attacks (theregister-security) | Apple Zero-Day Vulnerability Weaponized in Targeted Attacks (darkreading) |
| CVE-2026-86950 | Apple patches CoreGraphics zero-day already exploited in targeted attacks (theregister-security) | Apple CoreGraphics PoC Emerges as WhatsApp PDF Checks Hint at Possible Delivery Path (thehackernews) |
| CVE-2026-86950 | Apple patches CoreGraphics zero-day already exploited in targeted attacks (theregister-security) | Apple исправила использовавшуюся в атаках 0-day-уязвимость в CoreGraphics (xakep) |
| CVE-2026-86950 | Apple patches CoreGraphics zero-day already exploited in targeted attacks (theregister-security) | Уязвимость системного фреймворка Apple CoreGraphics операционных систем iOS, MacOS и iPadO (bdu-incident) |
| CVE-2026-86950 | Внеплановое обновление iOS 26.7.1: что исправила Apple (tg-zerodayalert) | Apple Zero-Day Vulnerability Weaponized in Targeted Attacks (darkreading) |
| CVE-2026-86950 | Внеплановое обновление iOS 26.7.1: что исправила Apple (tg-zerodayalert) | Apple CoreGraphics PoC Emerges as WhatsApp PDF Checks Hint at Possible Delivery Path (thehackernews) |
| CVE-2026-86950 | Внеплановое обновление iOS 26.7.1: что исправила Apple (tg-zerodayalert) | Apple исправила использовавшуюся в атаках 0-day-уязвимость в CoreGraphics (xakep) |
| CVE-2026-86950 | Внеплановое обновление iOS 26.7.1: что исправила Apple (tg-zerodayalert) | Уязвимость системного фреймворка Apple CoreGraphics операционных систем iOS, MacOS и iPadO (bdu-incident) |
| CVE-2026-86950 | Внеплановое обновление iOS 26.7.1: что исправила Apple (tg-zerodayalert) | Исследователи представили первый публичный PoC для CVE-2026-86950 в процессоре CoreGraphic (tg-true-secator) |
| CVE-2026-64507, CVE-2026-64508 | New Spectre v2 attack variant leaks Linux root password hash in minutes (bleepingcomputer) | Новый вариант атаки Spectre v2 - Branch Target Reuse (BTR), позволяет восстанавливать хэши (tg-true-secator) |
| CVE-2026-64507, CVE-2026-64508 | New Spectre v2 attack variant leaks Linux root password hash in minutes (bleepingcomputer) | Spectre bug is back, this time to haunt JIT engines (theregister-security) |
| CVE-2026-64507, CVE-2026-64508 | New Spectre v2 attack variant leaks Linux root password hash in minutes (bleepingcomputer) | Spectre обходит штатные защиты Linux через устаревшие записи процессора (tg-zerodayalert) |
| CVE-2026-64507 | New Spectre v2 attack variant leaks Linux root password hash in minutes (bleepingcomputer) | Уязвимость файлов arch/x86/include/asm/nospec-branch.h и arch/x86/kernel/cpu/bugs.c ядра о (tg-bdufstecru) |
| CVE-2026-88771, CVE-2026-88772 | Custom malware used in Citrix 0-day attacks targeting govt, banks, professional services (theregister-security) | Hackers exploit Citrix NetScaler zero-day to deploy web shells (bleepingcomputer) |
| CVE-2026-88771 | Custom malware used in Citrix 0-day attacks targeting govt, banks, professional services (theregister-security) | Уязвимость контроллера доставки приложений NetScaler ADC (ранее Citrix ADC) и системы конт (bdu-danger) |
| CVE-2026-88772 | Custom malware used in Citrix 0-day attacks targeting govt, banks, professional services (theregister-security) | Уязвимость контроллера доставки приложений NetScaler ADC (ранее Citrix ADC) и системы конт (bdu-incident) |
| CVE-2026-88772 | Custom malware used in Citrix 0-day attacks targeting govt, banks, professional services (theregister-security) | Citrix NetScaler CVE-2026-88772 Exploit Details Show Pre-Auth Path to Shellcode Execution (thehackernews) |
| CVE-2026-88771, CVE-2026-88772 | Custom malware used in Citrix 0-day attacks targeting govt, banks, professional services (theregister-security) | Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в Citrix NetScaler, связанной с р (tg-true-secator) |
| CVE-2026-88772 | Custom malware used in Citrix 0-day attacks targeting govt, banks, professional services (theregister-security) | В продолжение к предыдущему: в своем отчете Mandiant приводит дополнительные подробности о (tg-true-secator) |
| CVE-2026-88771, CVE-2026-88772 | Custom malware used in Citrix 0-day attacks targeting govt, banks, professional services (theregister-security) | Government, Finance Orgs Targeted in Weeks-Long NetScaler Zero-Day Attacks (securityweek) |
| CVE-2026-88771 | Custom malware used in Citrix 0-day attacks targeting govt, banks, professional services (theregister-security) | Citrix NetScaler прячет веб-шелл за CSS и оставляет superuser после взлома (tg-zerodayalert) |
| CVE-2026-64507, CVE-2026-64508 | Новый вариант атаки Spectre v2 - Branch Target Reuse (BTR), позволяет восстанавливать хэши (tg-true-secator) | Spectre bug is back, this time to haunt JIT engines (theregister-security) |
| CVE-2026-64507, CVE-2026-64508 | Новый вариант атаки Spectre v2 - Branch Target Reuse (BTR), позволяет восстанавливать хэши (tg-true-secator) | Spectre обходит штатные защиты Linux через устаревшие записи процессора (tg-zerodayalert) |
| CVE-2026-64507 | Новый вариант атаки Spectre v2 - Branch Target Reuse (BTR), позволяет восстанавливать хэши (tg-true-secator) | Уязвимость файлов arch/x86/include/asm/nospec-branch.h и arch/x86/kernel/cpu/bugs.c ядра о (tg-bdufstecru) |
| CVE-2026-88771 | Hackers exploit Citrix NetScaler zero-day to deploy web shells (bleepingcomputer) | Уязвимость контроллера доставки приложений NetScaler ADC (ранее Citrix ADC) и системы конт (bdu-danger) |
| CVE-2026-88772 | Hackers exploit Citrix NetScaler zero-day to deploy web shells (bleepingcomputer) | Уязвимость контроллера доставки приложений NetScaler ADC (ранее Citrix ADC) и системы конт (bdu-incident) |
| CVE-2026-88772 | Hackers exploit Citrix NetScaler zero-day to deploy web shells (bleepingcomputer) | Citrix NetScaler CVE-2026-88772 Exploit Details Show Pre-Auth Path to Shellcode Execution (thehackernews) |
| CVE-2026-88771, CVE-2026-88772 | Hackers exploit Citrix NetScaler zero-day to deploy web shells (bleepingcomputer) | Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в Citrix NetScaler, связанной с р (tg-true-secator) |
| CVE-2026-88772 | Hackers exploit Citrix NetScaler zero-day to deploy web shells (bleepingcomputer) | В продолжение к предыдущему: в своем отчете Mandiant приводит дополнительные подробности о (tg-true-secator) |
| CVE-2026-88771, CVE-2026-88772 | Hackers exploit Citrix NetScaler zero-day to deploy web shells (bleepingcomputer) | Government, Finance Orgs Targeted in Weeks-Long NetScaler Zero-Day Attacks (securityweek) |
| CVE-2026-88771 | Hackers exploit Citrix NetScaler zero-day to deploy web shells (bleepingcomputer) | Citrix NetScaler прячет веб-шелл за CSS и оставляет superuser после взлома (tg-zerodayalert) |
| CVE-2026-88771 | Уязвимость контроллера доставки приложений NetScaler ADC (ранее Citrix ADC) и системы конт (bdu-danger) | Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в Citrix NetScaler, связанной с р (tg-true-secator) |
| CVE-2026-88771 | Уязвимость контроллера доставки приложений NetScaler ADC (ранее Citrix ADC) и системы конт (bdu-danger) | Government, Finance Orgs Targeted in Weeks-Long NetScaler Zero-Day Attacks (securityweek) |
| CVE-2026-88771 | Уязвимость контроллера доставки приложений NetScaler ADC (ранее Citrix ADC) и системы конт (bdu-danger) | Citrix NetScaler прячет веб-шелл за CSS и оставляет superuser после взлома (tg-zerodayalert) |
| CVE-2026-88772 | Уязвимость контроллера доставки приложений NetScaler ADC (ранее Citrix ADC) и системы конт (bdu-incident) | Citrix NetScaler CVE-2026-88772 Exploit Details Show Pre-Auth Path to Shellcode Execution (thehackernews) |
| CVE-2026-88772 | Уязвимость контроллера доставки приложений NetScaler ADC (ранее Citrix ADC) и системы конт (bdu-incident) | Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в Citrix NetScaler, связанной с р (tg-true-secator) |
| CVE-2026-88772 | Уязвимость контроллера доставки приложений NetScaler ADC (ранее Citrix ADC) и системы конт (bdu-incident) | В продолжение к предыдущему: в своем отчете Mandiant приводит дополнительные подробности о (tg-true-secator) |
| CVE-2026-88772 | Уязвимость контроллера доставки приложений NetScaler ADC (ранее Citrix ADC) и системы конт (bdu-incident) | Government, Finance Orgs Targeted in Weeks-Long NetScaler Zero-Day Attacks (securityweek) |
| CVE-2026-86950 | Apple Zero-Day Vulnerability Weaponized in Targeted Attacks (darkreading) | Apple CoreGraphics PoC Emerges as WhatsApp PDF Checks Hint at Possible Delivery Path (thehackernews) |
| CVE-2026-86950 | Apple Zero-Day Vulnerability Weaponized in Targeted Attacks (darkreading) | Apple исправила использовавшуюся в атаках 0-day-уязвимость в CoreGraphics (xakep) |
| CVE-2026-86950 | Apple Zero-Day Vulnerability Weaponized in Targeted Attacks (darkreading) | Уязвимость системного фреймворка Apple CoreGraphics операционных систем iOS, MacOS и iPadO (bdu-incident) |
| CVE-2026-86950 | Apple Zero-Day Vulnerability Weaponized in Targeted Attacks (darkreading) | Исследователи представили первый публичный PoC для CVE-2026-86950 в процессоре CoreGraphic (tg-true-secator) |
| CVE-2026-88772 | Citrix NetScaler CVE-2026-88772 Exploit Details Show Pre-Auth Path to Shellcode Execution (thehackernews) | Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в Citrix NetScaler, связанной с р (tg-true-secator) |
| CVE-2026-88772 | Citrix NetScaler CVE-2026-88772 Exploit Details Show Pre-Auth Path to Shellcode Execution (thehackernews) | В продолжение к предыдущему: в своем отчете Mandiant приводит дополнительные подробности о (tg-true-secator) |
| CVE-2026-88772 | Citrix NetScaler CVE-2026-88772 Exploit Details Show Pre-Auth Path to Shellcode Execution (thehackernews) | Government, Finance Orgs Targeted in Weeks-Long NetScaler Zero-Day Attacks (securityweek) |
| CVE-2026-64507, CVE-2026-64508 | Spectre bug is back, this time to haunt JIT engines (theregister-security) | Spectre обходит штатные защиты Linux через устаревшие записи процессора (tg-zerodayalert) |
| CVE-2026-64507 | Spectre bug is back, this time to haunt JIT engines (theregister-security) | Уязвимость файлов arch/x86/include/asm/nospec-branch.h и arch/x86/kernel/cpu/bugs.c ядра о (tg-bdufstecru) |
| CVE-2026-88772 | Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в Citrix NetScaler, связанной с р (tg-true-secator) | В продолжение к предыдущему: в своем отчете Mandiant приводит дополнительные подробности о (tg-true-secator) |
| CVE-2026-88771, CVE-2026-88772 | Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в Citrix NetScaler, связанной с р (tg-true-secator) | Government, Finance Orgs Targeted in Weeks-Long NetScaler Zero-Day Attacks (securityweek) |
| CVE-2026-88771 | Mandiant сообщает об эксплуатации 0-day, CVE-2026-88772, в Citrix NetScaler, связанной с р (tg-true-secator) | Citrix NetScaler прячет веб-шелл за CSS и оставляет superuser после взлома (tg-zerodayalert) |
| CVE-2026-88772 | В продолжение к предыдущему: в своем отчете Mandiant приводит дополнительные подробности о (tg-true-secator) | Government, Finance Orgs Targeted in Weeks-Long NetScaler Zero-Day Attacks (securityweek) |
| CVE-2026-88771 | Government, Finance Orgs Targeted in Weeks-Long NetScaler Zero-Day Attacks (securityweek) | Citrix NetScaler прячет веб-шелл за CSS и оставляет superuser после взлома (tg-zerodayalert) |
| CVE-2026-73570 | Unauthenticated command injection on internet-facing mail servers: tracking CVE-2026-73570 (microsoft-research) | Attackers Exploit Zimbra Flaw to Deploy Web Shells and Harvest Authentication Secrets (thehackernews) |
| CVE-2026-73570 | Unauthenticated command injection on internet-facing mail servers: tracking CVE-2026-73570 (microsoft-research) | Zimbra Vulnerability Exploited in the Wild Prior to Public Disclosure (securityweek) |
| CVE-2026-73570 | Unauthenticated command injection on internet-facing mail servers: tracking CVE-2026-73570 (microsoft-research) | Microsoft catches hackers exploiting Zimbra bug before disclosure (theregister-security) |
| CVE-2026-76504 | Cisco warns of new SD-WAN zero-day exploited in attacks (bleepingcomputer) | Cisco Warns of Attackers Exploiting Critical Authentication Bypass in SD-WAN Manager (thehackernews) |
| CVE-2026-76504 | Cisco warns of new SD-WAN zero-day exploited in attacks (bleepingcomputer) | Cisco выпустила обновления для устранения критической 0-day в Catalyst SD-WAN Manager (отс (tg-true-secator) |
| CVE-2026-76504 | Cisco warns of new SD-WAN zero-day exploited in attacks (bleepingcomputer) | CISA Adds Exploited Cisco Catalyst SD-WAN Manager Auth Bypass to KEV (thehackernews) |
| CVE-2026-76504 | Cisco warns of new SD-WAN zero-day exploited in attacks (bleepingcomputer) | Уязвимость прикладного программного интерфейса централизованной системы управления сетью C (bdu-incident) |
| CVE-2026-76504 | Cisco warns of new SD-WAN zero-day exploited in attacks (bleepingcomputer) | Cisco закрыла критическую zero-day в Catalyst SD-WAN Manager с CVSS 9,8 (tg-zerodayalert) |
| CVE-2026-76504 | Cisco Warns of Attackers Exploiting Critical Authentication Bypass in SD-WAN Manager (thehackernews) | Cisco выпустила обновления для устранения критической 0-day в Catalyst SD-WAN Manager (отс (tg-true-secator) |
| CVE-2026-76504 | Cisco Warns of Attackers Exploiting Critical Authentication Bypass in SD-WAN Manager (thehackernews) | CISA Adds Exploited Cisco Catalyst SD-WAN Manager Auth Bypass to KEV (thehackernews) |
| CVE-2026-76504 | Cisco Warns of Attackers Exploiting Critical Authentication Bypass in SD-WAN Manager (thehackernews) | Уязвимость прикладного программного интерфейса централизованной системы управления сетью C (bdu-incident) |
| CVE-2026-76504 | Cisco Warns of Attackers Exploiting Critical Authentication Bypass in SD-WAN Manager (thehackernews) | Таинственные злоумышленники научились получать доступ к панели управления Cisco (cnews-safe) |
| CVE-2026-76504 | Cisco Warns of Attackers Exploiting Critical Authentication Bypass in SD-WAN Manager (thehackernews) | Cisco закрыла критическую zero-day в Catalyst SD-WAN Manager с CVSS 9,8 (tg-zerodayalert) |
| CVE-2026-84411 | CISA warns of critical pre-auth RCE flaw in MikroTik RouterOS (bleepingcomputer) | MikroTik's RouterOS has a near maximum severity bug: CISA urges updating ASAP (cybernews) |
| CVE-2026-84411 | CISA warns of critical pre-auth RCE flaw in MikroTik RouterOS (bleepingcomputer) | CISA предупреждает о критической RCE-уязвимости в MikroTik RouterOS (xakep) |
| CVE-2026-73570 | Attackers Exploit Zimbra Flaw to Deploy Web Shells and Harvest Authentication Secrets (thehackernews) | Zimbra Vulnerability Exploited in the Wild Prior to Public Disclosure (securityweek) |
| CVE-2026-73570 | Attackers Exploit Zimbra Flaw to Deploy Web Shells and Harvest Authentication Secrets (thehackernews) | Microsoft catches hackers exploiting Zimbra bug before disclosure (theregister-security) |
| CVE-2026-102489, CVE-2026-102490 | DIVD says Zammad zero-days enabled AI-driven network breach (bleepingcomputer) | Подкатили подробности инцидента со взломом Голландского института раскрытия уязвимостей (D (tg-true-secator) |
| CVE-2026-102489, CVE-2026-102490 | DIVD says Zammad zero-days enabled AI-driven network breach (bleepingcomputer) | Ирония судьбы (tg-alukatsky) |
| CVE-2026-102489, CVE-2026-102490 | DIVD says Zammad zero-days enabled AI-driven network breach (bleepingcomputer) | AI agents hacked the hackers, stealing email addresses from security research org (theregister-security) |
| CVE-2026-102489, CVE-2026-102490 | DIVD says Zammad zero-days enabled AI-driven network breach (bleepingcomputer) | CISA добавила в каталог KEV две уязвимости Zammad, включая выполнение кода через захват се (1275) |
| CVE-2026-86950 | Apple CoreGraphics PoC Emerges as WhatsApp PDF Checks Hint at Possible Delivery Path (thehackernews) | Apple исправила использовавшуюся в атаках 0-day-уязвимость в CoreGraphics (xakep) |
| CVE-2026-86950 | Apple CoreGraphics PoC Emerges as WhatsApp PDF Checks Hint at Possible Delivery Path (thehackernews) | Уязвимость системного фреймворка Apple CoreGraphics операционных систем iOS, MacOS и iPadO (bdu-incident) |
| CVE-2026-86950 | Apple CoreGraphics PoC Emerges as WhatsApp PDF Checks Hint at Possible Delivery Path (thehackernews) | Исследователи представили первый публичный PoC для CVE-2026-86950 в процессоре CoreGraphic (tg-true-secator) |
| CVE-2026-76504 | Cisco выпустила обновления для устранения критической 0-day в Catalyst SD-WAN Manager (отс (tg-true-secator) | CISA Adds Exploited Cisco Catalyst SD-WAN Manager Auth Bypass to KEV (thehackernews) |
| CVE-2026-76504 | Cisco выпустила обновления для устранения критической 0-day в Catalyst SD-WAN Manager (отс (tg-true-secator) | Уязвимость прикладного программного интерфейса централизованной системы управления сетью C (bdu-incident) |
| CVE-2026-76504 | Cisco выпустила обновления для устранения критической 0-day в Catalyst SD-WAN Manager (отс (tg-true-secator) | Таинственные злоумышленники научились получать доступ к панели управления Cisco (cnews-safe) |
| CVE-2026-76504 | Cisco выпустила обновления для устранения критической 0-day в Catalyst SD-WAN Manager (отс (tg-true-secator) | Cisco закрыла критическую zero-day в Catalyst SD-WAN Manager с CVSS 9,8 (tg-zerodayalert) |
| CVE-2026-76504 | CISA Adds Exploited Cisco Catalyst SD-WAN Manager Auth Bypass to KEV (thehackernews) | Уязвимость прикладного программного интерфейса централизованной системы управления сетью C (bdu-incident) |
| CVE-2026-76504 | CISA Adds Exploited Cisco Catalyst SD-WAN Manager Auth Bypass to KEV (thehackernews) | Таинственные злоумышленники научились получать доступ к панели управления Cisco (cnews-safe) |
| CVE-2026-76504 | CISA Adds Exploited Cisco Catalyst SD-WAN Manager Auth Bypass to KEV (thehackernews) | Cisco закрыла критическую zero-day в Catalyst SD-WAN Manager с CVSS 9,8 (tg-zerodayalert) |
| CVE-2026-64892 | Johnson Controls EasyIO Neo Series EC and CW Controllers (cisa-ics) | Контроллеры Johnson Controls EasyIO Neo допускают утечку учётных данных через HTTP и отлад (1275) |
| CVE-2026-93474, CVE-2026-95102 | Monta monta.app (cisa-ics) | Отсутствие аутентификации в WebSocket-интерфейсе Monta открывает путь к захвату управления (1275) |
| CVE-2026-15952, CVE-2026-15953 | ABB Protection and Control IED Manager PCM600 (cisa-ics) | Служба планировщика и обработка архивов в ABB PCM600 позволяют повысить привилегии и запис (1275) |
| CVE-2023-46604 | Armatura LLC Armatura One (cisa-ics) | CISA предупреждает о пяти уязвимостях в Armatura One, одна из них в каталоге активно экспл (1275) |
| CVE-2026-64893 | Johnson Controls EasyIO Neo Series EC and CW Controllers (cisa-ics) | Контроллеры Johnson Controls EasyIO Neo допускают утечку учётных данных через HTTP и отлад (1275) |
| CVE-2026-90444, CVE-2026-90445 | CISA Malcolm (cisa-ics) | Malcolm 26.06.0 закрывает 15 уязвимостей, включая внедрение команд через имя загруженного  (1275) |
| CVE-2026-101104, CVE-2026-96613 | Meari IoT Cloud Platform OpenAPI Service (cisa-ics) | Отсутствие проверки прав в Meari IoT Cloud Platform открывает доступ к чужим устройствам и (1275) |
| CVE-2026-73570 | Zimbra Vulnerability Exploited in the Wild Prior to Public Disclosure (securityweek) | Microsoft catches hackers exploiting Zimbra bug before disclosure (theregister-security) |
| CVE-2026-54154 | Kiteworks patches max severity code injection vulnerability (bleepingcomputer) | Более сотни уязвимостей в четырёх продуктах Kiteworks открывают путь к захвату учётных зап (1275) |
| CVE-2026-54154 | Kiteworks patches max severity code injection vulnerability (bleepingcomputer) | Kiteworks EPG получил 10 из 10 по CVSS: удалённая атака приводит к root (tg-zerodayalert) |
| CVE-2026-84411 | MikroTik's RouterOS has a near maximum severity bug: CISA urges updating ASAP (cybernews) | CISA предупреждает о критической RCE-уязвимости в MikroTik RouterOS (xakep) |
| CVE-2026-102489, CVE-2026-102490 | Подкатили подробности инцидента со взломом Голландского института раскрытия уязвимостей (D (tg-true-secator) | Ирония судьбы (tg-alukatsky) |
| CVE-2026-102489, CVE-2026-102490 | Подкатили подробности инцидента со взломом Голландского института раскрытия уязвимостей (D (tg-true-secator) | AI agents hacked the hackers, stealing email addresses from security research org (theregister-security) |
| CVE-2026-102489, CVE-2026-102490 | Подкатили подробности инцидента со взломом Голландского института раскрытия уязвимостей (D (tg-true-secator) | CISA добавила в каталог KEV две уязвимости Zammad, включая выполнение кода через захват се (1275) |
| CVE-2026-86950 | Apple исправила использовавшуюся в атаках 0-day-уязвимость в CoreGraphics (xakep) | Уязвимость системного фреймворка Apple CoreGraphics операционных систем iOS, MacOS и iPadO (bdu-incident) |
| CVE-2026-86950 | Apple исправила использовавшуюся в атаках 0-day-уязвимость в CoreGraphics (xakep) | Исследователи представили первый публичный PoC для CVE-2026-86950 в процессоре CoreGraphic (tg-true-secator) |
| CVE-2026-102489, CVE-2026-102490 | Ирония судьбы (tg-alukatsky) | AI agents hacked the hackers, stealing email addresses from security research org (theregister-security) |
| CVE-2026-102489, CVE-2026-102490 | Ирония судьбы (tg-alukatsky) | CISA добавила в каталог KEV две уязвимости Zammad, включая выполнение кода через захват се (1275) |
| CVE-2026-64507 | Spectre обходит штатные защиты Linux через устаревшие записи процессора (tg-zerodayalert) | Уязвимость файлов arch/x86/include/asm/nospec-branch.h и arch/x86/kernel/cpu/bugs.c ядра о (tg-bdufstecru) |
| CVE-2026-86950 | Уязвимость системного фреймворка Apple CoreGraphics операционных систем iOS, MacOS и iPadO (bdu-incident) | Исследователи представили первый публичный PoC для CVE-2026-86950 в процессоре CoreGraphic (tg-true-secator) |
| CVE-2026-104286 | Уязвимость графического интерфейса системы защиты электронной почты FortiMail, позволяющая (bdu-incident) | Fortinet warns of critical FortiMail flaw exploited in zero-day attacks (bleepingcomputer) |
| CVE-2026-104286 | Уязвимость графического интерфейса системы защиты электронной почты FortiMail, позволяющая (bdu-incident) | Critical FortiMail Zero-Day Flaw Exploited in Attacks Allows Unauthenticated Arbitrary Fil (thehackernews) |
| CVE-2026-104286 | Уязвимость графического интерфейса системы защиты электронной почты FortiMail, позволяющая (bdu-incident) | Обход каталога в FortiMail уже используют для записи произвольных файлов без аутентификаци (1275) |
| CVE-2026-104286 | Уязвимость графического интерфейса системы защиты электронной почты FortiMail, позволяющая (bdu-incident) | Exploited Fortinet FortiMail Zero-Day Calls for Urgent Action (securityweek) |
| CVE-2026-104286 | Уязвимость графического интерфейса системы защиты электронной почты FortiMail, позволяющая (bdu-incident) | CISA добавила в каталог активно эксплуатируемых уязвимостей обход пути в Fortinet FortiMai (1275) |
| CVE-2026-104286 | Уязвимость графического интерфейса системы защиты электронной почты FortiMail, позволяющая (bdu-incident) | Fortinet sounds the alarm over actively exploited FortiMail zero-day (theregister-security) |
| CVE-2026-104286 | Уязвимость графического интерфейса системы защиты электронной почты FortiMail, позволяющая (bdu-incident) | Fortinet предупреждает о критической уязвимости, которая активно используется в 0-day атак (tg-true-secator) |
| CVE-2026-76504 | Уязвимость прикладного программного интерфейса централизованной системы управления сетью C (bdu-incident) | Таинственные злоумышленники научились получать доступ к панели управления Cisco (cnews-safe) |
| CVE-2026-76504 | Уязвимость прикладного программного интерфейса централизованной системы управления сетью C (bdu-incident) | Cisco закрыла критическую zero-day в Catalyst SD-WAN Manager с CVSS 9,8 (tg-zerodayalert) |
| CVE-2026-102489, CVE-2026-102490 | AI agents hacked the hackers, stealing email addresses from security research org (theregister-security) | CISA добавила в каталог KEV две уязвимости Zammad, включая выполнение кода через захват се (1275) |
| CVE-2026-104286 | Fortinet warns of critical FortiMail flaw exploited in zero-day attacks (bleepingcomputer) | Critical FortiMail Zero-Day Flaw Exploited in Attacks Allows Unauthenticated Arbitrary Fil (thehackernews) |
| CVE-2026-104286 | Fortinet warns of critical FortiMail flaw exploited in zero-day attacks (bleepingcomputer) | Обход каталога в FortiMail уже используют для записи произвольных файлов без аутентификаци (1275) |
| CVE-2026-104286 | Fortinet warns of critical FortiMail flaw exploited in zero-day attacks (bleepingcomputer) | Exploited Fortinet FortiMail Zero-Day Calls for Urgent Action (securityweek) |
| CVE-2026-104286 | Fortinet warns of critical FortiMail flaw exploited in zero-day attacks (bleepingcomputer) | CISA добавила в каталог активно эксплуатируемых уязвимостей обход пути в Fortinet FortiMai (1275) |
| CVE-2026-104286 | Fortinet warns of critical FortiMail flaw exploited in zero-day attacks (bleepingcomputer) | Fortinet sounds the alarm over actively exploited FortiMail zero-day (theregister-security) |
| CVE-2026-104286 | Fortinet warns of critical FortiMail flaw exploited in zero-day attacks (bleepingcomputer) | Fortinet предупреждает о критической уязвимости, которая активно используется в 0-day атак (tg-true-secator) |
| CVE-2026-104286 | Critical FortiMail Zero-Day Flaw Exploited in Attacks Allows Unauthenticated Arbitrary Fil (thehackernews) | Обход каталога в FortiMail уже используют для записи произвольных файлов без аутентификаци (1275) |
| CVE-2026-104286 | Critical FortiMail Zero-Day Flaw Exploited in Attacks Allows Unauthenticated Arbitrary Fil (thehackernews) | Exploited Fortinet FortiMail Zero-Day Calls for Urgent Action (securityweek) |
| CVE-2026-104286 | Critical FortiMail Zero-Day Flaw Exploited in Attacks Allows Unauthenticated Arbitrary Fil (thehackernews) | CISA добавила в каталог активно эксплуатируемых уязвимостей обход пути в Fortinet FortiMai (1275) |
| CVE-2026-104286 | Critical FortiMail Zero-Day Flaw Exploited in Attacks Allows Unauthenticated Arbitrary Fil (thehackernews) | Fortinet sounds the alarm over actively exploited FortiMail zero-day (theregister-security) |
| CVE-2026-104286 | Critical FortiMail Zero-Day Flaw Exploited in Attacks Allows Unauthenticated Arbitrary Fil (thehackernews) | Fortinet предупреждает о критической уязвимости, которая активно используется в 0-day атак (tg-true-secator) |
| CVE-2026-104286 | Обход каталога в FortiMail уже используют для записи произвольных файлов без аутентификаци (1275) | Exploited Fortinet FortiMail Zero-Day Calls for Urgent Action (securityweek) |
| CVE-2026-104286 | Обход каталога в FortiMail уже используют для записи произвольных файлов без аутентификаци (1275) | CISA добавила в каталог активно эксплуатируемых уязвимостей обход пути в Fortinet FortiMai (1275) |
| CVE-2026-104286 | Обход каталога в FortiMail уже используют для записи произвольных файлов без аутентификаци (1275) | Fortinet sounds the alarm over actively exploited FortiMail zero-day (theregister-security) |
| CVE-2026-104286 | Обход каталога в FortiMail уже используют для записи произвольных файлов без аутентификаци (1275) | Fortinet предупреждает о критической уязвимости, которая активно используется в 0-day атак (tg-true-secator) |
| CVE-2026-104286 | Exploited Fortinet FortiMail Zero-Day Calls for Urgent Action (securityweek) | CISA добавила в каталог активно эксплуатируемых уязвимостей обход пути в Fortinet FortiMai (1275) |
| CVE-2026-104286 | Exploited Fortinet FortiMail Zero-Day Calls for Urgent Action (securityweek) | Fortinet sounds the alarm over actively exploited FortiMail zero-day (theregister-security) |
| CVE-2026-104286 | Exploited Fortinet FortiMail Zero-Day Calls for Urgent Action (securityweek) | Fortinet предупреждает о критической уязвимости, которая активно используется в 0-day атак (tg-true-secator) |
| CVE-2026-104286 | CISA добавила в каталог активно эксплуатируемых уязвимостей обход пути в Fortinet FortiMai (1275) | Fortinet sounds the alarm over actively exploited FortiMail zero-day (theregister-security) |
| CVE-2026-104286 | CISA добавила в каталог активно эксплуатируемых уязвимостей обход пути в Fortinet FortiMai (1275) | Fortinet предупреждает о критической уязвимости, которая активно используется в 0-day атак (tg-true-secator) |
| CVE-2026-54154 | Более сотни уязвимостей в четырёх продуктах Kiteworks открывают путь к захвату учётных зап (1275) | Kiteworks EPG получил 10 из 10 по CVSS: удалённая атака приводит к root (tg-zerodayalert) |
| CVE-2026-76504 | Таинственные злоумышленники научились получать доступ к панели управления Cisco (cnews-safe) | Cisco закрыла критическую zero-day в Catalyst SD-WAN Manager с CVSS 9,8 (tg-zerodayalert) |
| CVE-2025-49704, CVE-2025-49706, CVE-2025-53770 | Symantec reports Warlock ransomware group targets water, telecom, government organizations (industrialcyber) | Warlock ransomware breach SharePoint in water, telecom operator attacks (bleepingcomputer) |
| CVE-2026-104286 | Fortinet sounds the alarm over actively exploited FortiMail zero-day (theregister-security) | Fortinet предупреждает о критической уязвимости, которая активно используется в 0-day атак (tg-true-secator) |
| CVE-2026-63688 | Dell asks admins to patch max severity CSM flaws as soon as possible (bleepingcomputer) | Dell CSM Flaws Enable Unauthenticated Admin Access and Root on Kubernetes Nodes (thehackernews) |
| BDU:2026-15756 | Уязвимость программного обеспечения TrueConf Server связана с непринятием мер по нейтрализ (tg-bdufstecru) | Критическая уязвимость в TrueConf: патчимся немедленно! (BDU:2026-15756) (tg-cyberok) |
| BDU:2026-15756 | Уязвимость программного обеспечения TrueConf Server связана с непринятием мер по нейтрализ (tg-bdufstecru) | Пароль больше не нужен: критическая дыра в TrueConf отдаёт сервер атакующему (securitylab) |
| BDU:2026-15756 | Критическая уязвимость в TrueConf: патчимся немедленно! (BDU:2026-15756) (tg-cyberok) | Пароль больше не нужен: критическая дыра в TrueConf отдаёт сервер атакующему (securitylab) |
| CVE-2026-90970 | GitLab warns of critical RCE vulnerability in AI Gateway service (bleepingcomputer) | Некорректная обработка шаблонов подсказок в GitLab AI Gateway открывает путь к выполнению  (1275) |
