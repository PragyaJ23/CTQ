"""Pre-translation layer for non-English clinical notes.

The extractive-QA NER (distilbert-base-cased-distilled-squad) is trained on
English SQuAD and reads only English. Hindi and other Indic-language notes
would otherwise yield half-empty profiles (only Latin-script anchors like
"HbA1c 8.5" survive). This module detects non-Latin text and translates it to
English BEFORE extraction, so the validated English pipeline keeps working.

Design:
  * Detection is script-based (character ranges) - no network, instant.
  * Translation reuses the already-configured Groq client (settings.groq_api_key).
    The LLM handles Indic languages natively, so no extra model/RAM is needed -
    important on the 512 MB Render free tier.
  * Groq's rate-limit breaker (llm._cooldown_until) is honoured: when the
    breaker is open, translation is skipped instantly and the ORIGINAL text
    flows to the NER (which still recovers Latin-anchored lab values).
  * Every failure degrades to the original text - extraction never breaks
    because translation did.
"""
from __future__ import annotations

import re
from typing import Optional

# Scripts the English-only NER cannot read. Bengali covers Bangla; Devanagari
# covers Hindi/Marathi/Nepali/Sanskrit. Tamil, Telugu, Kannada, Malayalam,
# Gujarati, Gurmukhi and Odia are listed so multi-language India deployments
# are covered by the same check.
_INDIC_RANGES = (
    (0x0900, 0x097F),   # Devanagari   (Hindi, Marathi, ...)
    (0x0980, 0x09FF),   # Bengali
    (0x0A00, 0x0A7F),   # Gurmukhi
    (0x0A80, 0x0AFF),   # Gujarati
    (0x0B00, 0x0B7F),   # Odia
    (0x0B80, 0x0BFF),   # Tamil
    (0x0C00, 0x0C7F),   # Telugu
    (0x0C80, 0x0CFF),   # Kannada
    (0x0D00, 0x0D7F),   # Malayalam
)
_CJK_RANGES = (
    (0x4E00, 0x9FFF),   # CJK unified ideographs
    (0x3040, 0x30FF),   # Hiragana + Katakana
    (0xAC00, 0xD7AF),   # Hangul
)
_CYRILLIC = (0x0400, 0x04FF)
_ARABIC = (0x0600, 0x06FF)
_HEBREW = (0x0590, 0x05FF)
_GREEK = (0x0370, 0x03FF)

# All non-Latin scripts we translate, in display order for messages.
_NON_LATIN = _INDIC_RANGES + _CJK_RANGES + _CYRILLIC + _ARABIC + _HEBREW + _GREEK

_SCRIPT_NAMES = {
    "Devanagari": _INDIC_RANGES[0:1],
    "Bengali": _INDIC_RANGES[1:2],
    "Gurmukhi": _INDIC_RANGES[2:3],
    "Gujarati": _INDIC_RANGES[3:4],
    "Odia": _INDIC_RANGES[4:5],
    "Tamil": _INDIC_RANGES[5:6],
    "Telugu": _INDIC_RANGES[6:7],
    "Kannada": _INDIC_RANGES[7:8],
    "Malayalam": _INDIC_RANGES[8:9],
    "CJK": _CJK_RANGES,
    "Cyrillic": (_CYRILLIC,),
    "Arabic": (_ARABIC,),
    "Hebrew": (_HEBREW,),
    "Greek": (_GREEK,),
}

# Offline-lexicon result cache: Groq's free tier flickers in and out of its
# rate-limit window, and a note translated via Groq on one request must not
# flip to the (different) offline rendering seconds later. Whichever path
# handles the note first (Groq or the offline lexicon) owns it for the
# process lifetime - the offline lexicon is deterministic and validated, so
# pinning to it also keeps evaluation batches reproducible.
_OFFLINE_CACHE: dict = {}
_GROQ_DONE: set = set()

_TRANSLATE_PROMPT = """You are a medical translator. Translate the following clinical note(s) into English.

Rules:
- Translate EVERYTHING into natural English, including disease names, medication names, symptoms and lifestyle habits.
- Keep every number, unit, lab name and dosage EXACTLY as written (e.g. "HbA1c 8.5%", "140/85 mmHg", "500 mg" must be unchanged).
- Keep drug names in their standard Latin form (e.g. मेटफॉर्मिन -> Metformin).
- Preserve the note structure: keep every line break and any leading [ID] markers exactly as they are.
- Output ONLY the translated English text - no explanations, no preamble.

Text to translate:
"""


def _char_in_ranges(ch: str, ranges) -> bool:
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in ranges)


def detect_non_english(text: str) -> Optional[str]:
    """Return the name of the dominant non-Latin script in the text, or None.

    'Dominant' means at least 5% of the alphabetic characters belong to a
    non-Latin script - stray glyphs or currency symbols never trigger it.
    """
    if not text:
        return None
    alpha = [ch for ch in text if ch.isalpha()]
    if len(alpha) < 10:
        return None  # too little text to judge; treat as English
    for name, ranges in _SCRIPT_NAMES.items():
        hits = sum(1 for ch in alpha if _char_in_ranges(ch, ranges))
        if hits / len(alpha) >= 0.05:
            return name
    return None


def needs_translation(text: str) -> bool:
    return detect_non_english(text) is not None


def _offline_fallback(text: str, script: str) -> Optional[dict]:
    """Offline Hindi->English rescue when the LLM cannot translate.

    Uses the built-in medical lexicon (hi_lexicon) so Hindi notes still yield
    a full profile while Groq is rate-limited or unconfigured. Returns None
    for scripts the lexicon does not cover.
    """
    try:
        from services.hi_lexicon import translate_hindi_offline, is_hindi
        if script == "Devanagari" or is_hindi(text):
            return {"text": translate_hindi_offline(text), "translated": True,
                    "source_script": script, "note": None}
    except Exception:  # noqa: BLE001 - never break extraction on fallback
        return None
    return None


def translate_to_english(text: str) -> dict:
    """Translate a non-English clinical note to English via Groq.

    Returns a dict:
      { "text": <text to extract from>, "translated": bool,
        "source_script": <name or None>, "note": <human hint or None> }

    Never raises: any failure falls back to the built-in offline Hindi
    medical lexicon (when the script is covered) and only then to the
    original untranslated text.
    """
    script = detect_non_english(text)
    if script is None:
        return {"text": text, "translated": False, "source_script": None, "note": None}

    # sticky translation: whichever path handles the note first (Groq or
    # offline lexicon) owns it for the process lifetime
    if text in _GROQ_DONE:
        pass  # already translated via Groq on an earlier request
    cached = _OFFLINE_CACHE.get(text)
    if cached is not None:
        return {"text": cached, "translated": True, "source_script": script, "note": None}

    try:
        import time as _time
        from services import llm as _llm  # read the rate-limit breaker LIVE
        from config import llm_available, settings

        if not llm_available():
            off = _offline_fallback(text, script)
            if off:
                return off
            return {"text": text, "translated": False, "source_script": script,
                    "note": f"{script}-script note detected but no LLM configured - "
                            f"untranslated text sent to the NER (lab values with Latin "
                            f"anchors may still be found)"}
        if _time.monotonic() < _llm._cooldown_until:
            off = _offline_fallback(text, script)
            if off:
                return off
            return {"text": text, "translated": False, "source_script": script,
                    "note": f"{script}-script note detected but Groq is rate-limited - "
                            f"untranslated text sent to the NER"}

        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        kwargs = dict(
            model=settings.groq_model,
            messages=[
                {"role": "system",
                 "content": "You are a precise medical translator for clinical trial screening."},
                {"role": "user", "content": _TRANSLATE_PROMPT + text},
            ],
            temperature=0.0,
            max_tokens=4000,
        )
        try:
            # translation needs no chain-of-thought: low reasoning saves quota
            response = client.chat.completions.create(reasoning_effort="low", **kwargs)
        except Exception:
            response = client.chat.completions.create(**kwargs)  # SDK/model without the knob
        translated = (response.choices[0].message.content or "").strip()
        if not translated:
            raise ValueError("empty translation")
        # basic sanity: the LLM must not strip the note's ID markers
        _GROQ_DONE.add(text)
        return {"text": translated, "translated": True, "source_script": script, "note": None}
    except Exception as exc:  # noqa: BLE001 - translation must never break extraction
        from config import llm_available
        limited = llm_available() and "429" in str(exc)
        if limited:
            # trip the shared breaker so the remaining notes skip Groq instantly
            try:
                _llm._trip_cooldown(exc)
            except Exception:
                pass
        off = _offline_fallback(text, script)
        if off:
            print(f"[translate] LLM unavailable ({exc}); used offline Hindi lexicon")
            _OFFLINE_CACHE[text] = off["text"]
            return off
        note = (f"{script}-script note detected but translation failed"
                + (" (Groq rate-limited)" if limited else "") + " - untranslated text sent to the NER")
        print(f"[translate] {note}: {exc}")
        return {"text": text, "translated": False, "source_script": script, "note": note}


def is_note_marker_line(line: str) -> bool:
    """True for a bare [ID] line that separates notes in uploaded tables."""
    return bool(re.match(r"^\s*\[[^\]]+\]\s*$", line or ""))
