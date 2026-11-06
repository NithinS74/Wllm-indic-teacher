"""Supported languages and their model-facing identifiers.

Language identifiers verified against:
- IndicConformer README (short codes: hi, kn, ta, te, ml, ...)
- IndicTrans2 README (script-tagged codes: eng_Latn, hin_Deva, kan_Knda, ...)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Language:
    key: str                 # stable API key used by the frontend
    label: str               # display name
    indictrans: str          # IndicTrans2 language identifier
    indicconformer: str      # IndicConformer short language code
    script: str
    param1_native: bool = True  # can Param-1 read this language natively?


LANGUAGES: List[Language] = [
    Language("en", "English", "eng_Latn", "en", "Latin", True),
    Language("hi", "Hindi", "hin_Deva", "hi", "Devanagari", True),
    Language("kn", "Kannada", "kan_Knda", "kn", "Kannada", False),
    Language("ta", "Tamil", "tam_Taml", "ta", "Tamil", False),
    Language("te", "Telugu", "tel_Telu", "te", "Telugu", False),
    Language("ml", "Malayalam", "mal_Mlym", "ml", "Malayalam", False),
]

_BY_KEY: Dict[str, Language] = {l.key: l for l in LANGUAGES}


def get_language(key: str) -> Language:
    if key not in _BY_KEY:
        from app.core.errors import ValidationAppError
        raise ValidationAppError(
            f"Unsupported language '{key}'.",
            detail={"supported": list(_BY_KEY.keys())},
        )
    return _BY_KEY[key]


def language_keys() -> List[str]:
    return list(_BY_KEY.keys())
