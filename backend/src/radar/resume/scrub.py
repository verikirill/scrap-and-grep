"""Remove contact details from resume text before anything else sees it.

The extractor needs the professional part of a resume: roles, duties, tools.
Addresses, phone numbers and the like are dropped first, so they reach neither
the language model nor the database. This is pattern matching, not a guarantee:
an unusual layout can slip through, which is one more reason the text itself is
never stored.
"""

import re

# Every pattern here runs over text an outsider wrote, so none of them may
# backtrack without bound: repetitions are capped and no class crosses a line
# break where the pattern is anchored to line starts. A file of blank lines or
# of one endless word must cost linear time, not minutes.
_EMAIL_RE = re.compile(r"[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63}){1,8}")
_URL_RE = re.compile(r"(?:https?://|www\.)\S+|\b(?:t\.me|vk\.com|linkedin\.com|github\.com)/\S+")
_HANDLE_RE = re.compile(r"(?<![\w@])@[A-Za-z][\w.]{3,64}")
# A run of digits with the usual separators, within one line. Whether it is a
# phone number is decided by the number of digits: "2020 - 2023" has the same
# shape.
_PHONE_RE = re.compile(r"(?<![\w.])\+?\d[\d \t()\-]{8,30}\d(?!\w)")
_PHONE_MIN_DIGITS = 10
# Leading list and Markdown markers are skipped: "- **Телефон:** ..." counts.
_PERSONAL_LINE_RE = re.compile(
    r"^[ \t*_#>|-]{0,12}(?:дата[ \t]+рождения|родил(?:ся|ась)|возраст|адрес|место[ \t]+жительства|"
    r"проживает|город[ \t]+проживания|гражданство|семейное[ \t]+положение|пол|телефон|тел\.?|"
    r"моб\.?|e-?mail|почта|эл\.?[ \t]*почта|контакты|telegram|телеграм|skype|whatsapp|инн|снилс|"
    r"паспорт|date[ \t]+of[ \t]+birth|born|age|address|location|phone|mobile|citizenship|"
    r"nationality|marital[ \t]+status|gender|contacts?)\b[^\n]*$",
    re.IGNORECASE | re.MULTILINE,
)
_NAME_LINE_RE = re.compile(r"[A-ZА-ЯЁ][a-zа-яё-]{0,40}(?:[ \t]+[A-ZА-ЯЁ][a-zа-яё-]{0,40}){1,3}")
# Longer lines are never a name; checking them would only cost time.
_NAME_MAX_LENGTH = 80
# A capitalised line is a job title rather than a name if it holds one of these.
_TITLE_STEMS = (
    "инженер", "специалист", "руководител", "директор", "аналитик", "разработчик",
    "администратор", "менеджер", "архитектор", "начальник", "эксперт", "консультант",
    "резюме", "опыт", "навык", "образован", "engineer", "manager", "developer", "analyst",
    "architect", "administrator", "specialist", "director", "lead", "head", "resume",
    "summary", "experience", "skills", "education", "curriculum",
)  # fmt: skip
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_NAME_SCAN_LINES = 6


def _is_name(line: str) -> bool:
    stripped = line.strip(" #*_\t")
    if len(stripped) > _NAME_MAX_LENGTH or not _NAME_LINE_RE.fullmatch(stripped):
        return False
    lowered = stripped.lower()
    return not any(stem in lowered for stem in _TITLE_STEMS)


def _drop_phone(match: re.Match[str]) -> str:
    found = match.group()
    return " " if sum(char.isdigit() for char in found) >= _PHONE_MIN_DIGITS else found


def scrub(text: str) -> str:
    """Drop contact lines, links, addresses, phone numbers and the name line."""
    text = _PERSONAL_LINE_RE.sub("", text)
    for pattern in (_EMAIL_RE, _URL_RE, _HANDLE_RE):
        text = pattern.sub(" ", text)
    text = _PHONE_RE.sub(_drop_phone, text)
    lines = text.splitlines()
    # A resume opens with the person's name; look for it only at the very top,
    # further down a capitalised pair of words is a product or a company.
    seen = 0
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if _is_name(line):
            lines[index] = ""
        seen += 1
        if seen >= _NAME_SCAN_LINES:
            break
    cleaned = "\n".join(line.rstrip() for line in lines)
    return _BLANK_LINES_RE.sub("\n\n", cleaned).strip()
