"""Shared text utilities for evaluation: normalization for Indic + Latin scripts."""
from __future__ import annotations

import re
import unicodedata
from typing import List

# Common English punctuation / fillers stripped before scoring
_PUNCT = re.compile(r"[^\w\s\u0900-\u097F\u0980-\u09FF\u0900-\u097F"
                    r"\u0B80-\u0BFF\u0C00-\u0C7F\u0D00-\u0D7F]+",
                    re.UNICODE)
_WS = re.compile(r"\s+")

# Devanagari/Latin danda and quotes
_TRANS = str.maketrans({
    "।": " ",  # Devanagari danda
    "٬": " ",  # Arabic comma
    "“": '"', "”": '"', "‘": "'", "’": "'",
    "—": "-", "–": "-",
})


def normalize(text: str, *, lowercase: bool = True,
              strip_punct: bool = True) -> str:
    """Normalize text for WER/CER comparisons.

    - Unicode NFC
    - remove zero-width and joiners common in Indic scripts
    - unify punctuation
    - optional lowercase (safe for Latin; Indic scripts are caseless)
    """
    if text is None:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("‌", "").replace("‍", "")  # ZWNJ/ZWJ
    text = text.replace("﻿", "")
    text = text.translate(_TRANS)
    if lowercase:
        text = text.lower()
    if strip_punct:
        text = _PUNCT.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    return text


def tokenize_words(text: str) -> List[str]:
    norm = normalize(text)
    return [w for w in norm.split(" ") if w]


def tokenize_chars(text: str) -> List[str]:
    """Character tokens ignoring spaces (standard CER practice)."""
    norm = normalize(text, strip_punct=True)
    return [c for c in norm if not c.isspace()]
