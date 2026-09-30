"""Offline Hindi -> English medical lexicon used when the LLM is unavailable.

Groq's free tier exhausts frequently, and the previous behaviour degraded to
"sending raw Devanagari to the English-only NER" which extracted almost
nothing - users saw the "could not be translated" warning and an empty
profile. This module maps the standard Hindi clinical vocabulary to the exact
English terms the ML NER and its follow-up questions already understand
(mirroring ml_ner.py's condition/medication/symptom/lifestyle patterns), so a
Hindi note still yields a complete profile when Groq is rate-limited or the
key is missing.

This is deliberately a *medical* lexicon, not general translation: it covers
the closed vocabulary real clinical notes use (diseases, drugs, symptoms,
habits, organs, numbers' phrasing). Non-medical filler becomes neutral
English glue ("the", "and", ...) which the extractive-QA model handles
gracefully because it reads the whole sentence for context.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Multi-word phrases FIRST (longest-match wins), then single words.
# Values are the exact strings the English extraction layer expects.
# ---------------------------------------------------------------------------

# Order matters: longer keys are replaced before their substrings.
_PHRASES = {
    # --- demographics -------------------------------------------------------
    "वर्षीय": "year-old",
    "वर्ष का": "years old",
    "वर्ष की": "years old",
    "वर्ष के": "years old",
    "वर्षों से": "for years",
    "वर्षों": "years",
    "वर्ष": "year",
    "महीने की": "months pregnant",   # "5 महीने की गर्भवती" -> "5 months pregnant"
    "महीने": "months",
    "महीना": "month",
    "उम्र": "age",
    "पुरुष": "man male",
    "महिला": "woman female",
    "मरीज": "patient",
    "मरीज़": "patient",
    "रोगी": "patient",
    # --- diseases / conditions ---------------------------------------------
    "टाइप-2 डायबिटीज": "type 2 diabetes",
    "टाइप 2 डायबिटीज": "type 2 diabetes",
    "डायबिटीज": "diabetes",
    "मधुमेह": "diabetes",
    "शुगर": "blood sugar",
    "उच्च रक्तचाप": "hypertension high blood pressure",
    "हृदय विफलता": "heart failure",
    "हृदय संबंधी": "cardiac heart",
    "हृदय": "heart",
    "हार्ट फेल्योर": "heart failure",
    "हार्ट": "heart",
    "कैंसर": "cancer",
    "किडनी की बीमारी": "kidney disease",
    "किडनी": "kidney",
    "गुर्दा": "kidney",
    "सर्जरी": "surgery",
    "ऑपरेशन": "surgery",
    "बीमारी": "disease",
    "पीड़ित": "suffering from diagnosed with",
    "निदान": "diagnosed",
    "जांच": "test examination",
    "रिपोर्ट": "report",
    # --- medications --------------------------------------------------------
    "मेटफॉर्मिन": "Metformin",
    "ग्लिमेपिराइड": "Glimepiride",
    "एम्लोडिपिन": "Amlodipine",
    "फ्यूरोसेमाइड": "Furosemide",
    "इंसुलिन": "Insulin",
    "दवा": "medicine medication",
    "इलाज": "treatment",
    "समस्या": "problem",
    "पेट": "stomach",
    "सक्रिय": "active",
    "अन्य": "other",
    "गंभीर": "serious",
    "प्रकार": "kind type",
    "किसी": "any",
    "या": "or",
    "तथा": "and",
    "एवं": "and",
    "दवाओं": "medications",
    "दवाएं": "medications",
    "दवाइयां": "medications",
    "डॉक्टर": "doctor",
    # --- symptoms -----------------------------------------------------------
    "सांस लेने में तकलीफ": "shortness of breath",
    "सांस फूलना": "shortness of breath",
    "सांस": "breath",
    "पैरों में सूजन": "leg swelling",
    "सूजन": "swelling",
    "पैरों": "legs",
    "थकान": "fatigue",
    "कमजोरी": "weakness",
    "प्यास": "thirst",
    "पेशाब": "urination",
    "चक्कर": "dizziness",
    "सिरदर्द": "headache",
    "सीने में दर्द": "chest pain",
    "जोड़ों में दर्द": "joint pain",
    "दर्द": "pain",
    "बुखार": "fever",
    "खांसी": "cough",
    "उलटी": "vomiting",
    "जी मिचलाना": "nausea",
    # --- labs ---------------------------------------------------------------
    "क्रिएटिनिन": "creatinine",
    "रक्तचाप": "blood pressure",
    "व्रत के समय ग्लूकोज": "fasting glucose",
    "खाली पेट ग्लूकोज": "fasting glucose",
    "फास्टिंग ग्लूकोज": "fasting glucose",
    "वजन": "weight",
    "कद": "height",
    # --- lifestyle ----------------------------------------------------------
    "धूम्रपान नहीं करता": "does not smoke never smoked",
    "धूम्रपान नहीं करती": "does not smoke never smoked",
    "धूम्रपान": "smoking",
    "शराब का सेवन": "alcohol use",
    "शराब": "alcohol",
    "गर्भवती नहीं": "not pregnant",
    "गर्भवती": "pregnant",
    "कभी-कभी": "sometimes occasionally",
    "कभी कभी": "sometimes occasionally",
    "हाल की": "recent",
    "हाल ही में": "recently",
    "वर्तमान में": "currently",
    "वर्तमान": "current",
    "पिछले": "previous last past",
    "पहले": "previously before",
    "इतिहास": "history",
    "लक्षण": "symptoms",
    "नियमित": "regular",
    "व्यायाम": "exercise",
    "आहार": "diet",
    "योजना": "planning",
    "शुरू": "started starting",
    "सलाह": "advised",
    "स्थिर": "stable",
    "ब्लड प्रेशर": "blood pressure",
    "सेमी": "cm",
    "किलो": "kg",
    "पता चला": "diagnosed",
    "स्वस्थ": "healthy",
    "एलर्जी": "allergy",
    "नियंत्रित": "controlled",
    "साफ": "normal",
    "ठीक": "normal fine",
    "साल्बुटामोल": "Salbutamol",
    "ग्लाइमेपिराइड": "Glimepiride",
    "सामान्य": "normal",
    "हल्की": "mild",
    "संभावित": "possible suspected",
    "अधिक": "high",
    "लंबे समय से": "for a long time",
    # --- negations / glue (the NER's negation logic reads these) ------------
    "नहीं है": "no not present",
    "नहीं": "not no never",
    "कोई": "any no",
    "का कोई इतिहास नहीं": "no history of",
    "ज्ञात": "known",
    "उपलब्ध नहीं": "not available unknown",
    "है": "is",
    "हैं": "is",
    "था": "was",
    "थी": "was",
    "करता है": "does",
    "करती हैं": "does",
    "ले रहा है": "taking",
    "ले रही हैं": "taking",
    "और": "and",
    "यह": "this",
    "वह": "he she",
    "उसे": "he she",
    "उन्हें": "she",
    "के लिए": "for",
    "से": "from since",
    "में": "in",
    "की": "of",
    "का": "of",
    "के": "of",
    "एक": "a one",
    "दो बार": "twice daily two times",
    "तीन बार": "three times daily",
    "बार": "times",
    "दिन": "day",
    "रात": "night",
    "सप्ताह": "week",
}

# Single Devanagari digits -> ASCII (notes often mix scripts).
_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# Latin fragments that are safe to keep as-is (handled by skipping them in
# _convert; nothing to do here - they pass through untouched).

# \w + Devanagari (excluding the danda punctuation 0964-0965) + % . / - so
# decimals ("7.8"), units ("mg/dL") and doses ("500 mg") stay in one token
_WORD_RE = re.compile(r"[\w\u0900-\u0963\u0966-\u097F%./-]+", re.UNICODE)

# Devanagari word characters (including matras/virama) for dictionary lookup.
_HI_WORD_RE = re.compile(r"[\u0900-\u097F]+", re.UNICODE)


def _lookup(word: str) -> str | None:
    """Dictionary hit for a Devanagari word, with light inflection handling."""
    if word in _PHRASES:
        return _PHRASES[word]
    # strip common inflectional endings to hit the stem
    for suffix in ("ों", "े", "ी", "ाएं", "यों", "ने", "को"):
        stem = word[: -len(suffix)]
        if len(stem) >= 2 and stem in _PHRASES:
            return _PHRASES[stem]
    return None


def translate_hindi_offline(text: str) -> str:
    """Best-effort offline Hindi->English conversion for clinical notes.

    Multi-word phrase replacements run first over the whole text; any
    remaining Devanagari words are mapped individually, and unknown words are
    dropped. Latin words (drug names, "HbA1c", "mg/dL", numbers) pass through
    unchanged, so lab anchors always survive.
    """
    if not text:
        return text
    out = text.translate(_DIGITS)

    # sentence boundaries first: the danda lives inside the Devanagari block,
    # and the English condition/negation analysers split on "." - converting
    # it early keeps sentence-level logic working on the translated text.
    out = out.replace("\u0964", ". ").replace("\u0965", ". ")

    # Hindi negates AFTER the disease ("...का कोई इतिहास नहीं है"); English
    # negation logic in ml_ner reads BEFORE the span, so move the negation in
    # front: "X का [कोई] [ज्ञात] इतिहास नहीं" -> "no history of X".
    out = re.sub(r"([\u0900-\u097F][\u0900-\u097F ]*?)\s+का\s+(?:कोई\s+)?(?:ज्ञात\s+)?इतिहास\s+नहीं",
                 r" no history of \1", out)
    # "कोई ज्ञात X नहीं" -> "no known X"
    out = re.sub(r"कोई\s+ज्ञात\s+([\u0900-\u097F][\u0900-\u097F ]*?)\s+नहीं",
                 r" no known \1", out)

    # 1) phrase pass - longest keys first so "उच्च रक्तचाप" wins over "रक्तचाप"
    for hi in sorted(_PHRASES, key=len, reverse=True):
        if hi in out:
            out = out.replace(hi, " " + _PHRASES[hi] + " ")

    # 2) word pass - map whatever Devanagari is left, drop unknown words
    pieces = []
    for m in _WORD_RE.finditer(out):
        tok = m.group(0)
        if _HI_WORD_RE.fullmatch(tok):
            en = _lookup(tok)
            if en:
                pieces.append(en)
            # unknown Hindi word: dropped (neutral glue keeps grammar readable)
        else:
            pieces.append(tok)
    result = " ".join(pieces)

    # 3) tidy: collapse the spacing the phrase pass introduced
    result = re.sub(r"\s+([,.;:%])", r"\1", result)
    result = re.sub(r"\s{2,}", " ", result).strip()
    return result


def is_hindi(text: str) -> bool:
    """True when the text contains enough Devanagari to need it (>=5% of
    alphabetic characters, same threshold as translate.detect_non_english)."""
    alpha = [ch for ch in (text or "") if ch.isalpha()]
    if len(alpha) < 10:
        return False
    hits = sum(1 for ch in alpha if "\u0900" <= ch <= "\u097F")
    return hits / len(alpha) >= 0.05
