"""Filters shared by all company agents (stage 8, docs/agents/company-agents.md).

Code filters only what is certain: Israel + keywords. Everything else (field, region, days, experience)
belongs to the brain - better an extra job the brain filters than a job the code swallowed.

is_israel         is any of the job's locations in Israel (country code or a name from config/sources.json)
matching_keyword  the first keyword found in the title or the full text, as a whole word, or None
html_to_text      job description HTML -> plain text, keeping paragraph and list breaks
"""

import re
from functools import lru_cache
from html import unescape
from html.parser import HTMLParser

HEBREW = re.compile(r"[֐-׿]")
HEBREW_PREFIXES = "ולהבמשכ"  # ו ל ה ב מ ש כ - one-letter prefixes glued to a Hebrew word


def _word_pattern(word: str) -> str:
    """One keyword as a whole-word regex.

    English: "Intern" also matches "Interns", never "International" / "internal".
    Hebrew: "סטודנט" also matches "לסטודנטים" / "סטודנטית" (prefixes and endings are part of the word).
    Multi-word keywords allow a space or hyphen between words ("Entry Level", "Entry-Level").
    """
    parts = [re.escape(p) for p in word.split()]
    body = r"[\s-]+".join(parts)
    if HEBREW.search(word):
        return rf"(?<!\w)[{HEBREW_PREFIXES}]{{0,3}}{body}[א-ת]*(?!\w)"
    return rf"(?<!\w){body}s?(?!\w)"


@lru_cache(maxsize=None)
def _keywords_regex(words: tuple[str, ...]) -> re.Pattern:
    return re.compile("|".join(f"({_word_pattern(w)})" for w in words), re.IGNORECASE)


def matching_keyword(title: str | None, text: str | None, words: list[str]) -> str | None:
    """The keyword that let the job in (title first, then full text), or None. Used for the run report too."""
    regex = _keywords_regex(tuple(words))
    for field in (title, text):
        m = regex.search(field or "")
        if m:
            return words[m.lastindex - 1]
    return None


@lru_cache(maxsize=None)
def _names_regex(names: tuple[str, ...]) -> re.Pattern:
    return re.compile("|".join(rf"(?<!\w){re.escape(n)}(?!\w)" for n in names), re.IGNORECASE)


def is_israel(location: str | None, country: str | None, israel: dict) -> bool:
    """`israel` is the "israel" block of config/sources.json. A job in several places passes if one is in Israel."""
    if country and country.upper() in israel["country_codes"]:
        return True
    return bool(_names_regex(tuple(israel["names"])).search(location or ""))


class _TextExtractor(HTMLParser):
    BREAKS = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BREAKS:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")

    def handle_endtag(self, tag):
        if tag in self.BREAKS:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(html: str | None) -> str:
    """Plain text of a job description. Also handles HTML that arrives escaped (&lt;p&gt;, as Greenhouse sends it)."""
    if not html:
        return ""
    if "&lt;" in html:
        html = unescape(html)
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    text = "".join(parser.parts).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
