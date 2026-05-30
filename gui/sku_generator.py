"""
Couch Petato — Internal SKU Generator
Format: CP-{MODEL}-{SUPPLIER}-{COLOR}-{FINISH}
Example: CP-CMR-MRC-14VEL-OAK
"""
import re

VOWELS = frozenset("AEIOU")

# Known fabric/upholstery suppliers → abbreviation
SUPPLIER_CODES = {
    "mercis":             "MRC",
    "fabric library":     "FBL",
    "symphony interiors": "SI",
    "symphony":           "SI",
}

# Known model names → abbreviation (auto-derived if not listed)
MODEL_CODES = {
    "cami round":   "CMR",
    "reacher box":  "RCH",
    "lisa round":   "LSR",
    "coco seater":  "CCS",
    "acrylic box":  "ACB",
}


def _first_alnum(word: str) -> str:
    """Return the first alphanumeric character of a word, or ''."""
    for ch in word:
        if ch.isalnum():
            return ch
    return ""


def _split_words(name: str):
    """Split on whitespace, hyphens, underscores, slashes; drop empty tokens."""
    return [w for w in re.split(r"[\s\-_/]+", name.upper()) if w]


def model_abbr(name: str) -> str:
    """Derive model abbreviation — first alnum char of each word.
    'Cami Round'  → 'CR'
    'Cami-Round'  → 'CR'
    'Bed 3 Pro'   → 'B3P'
    """
    if not name:
        return ""
    key = name.strip().lower()
    if key in MODEL_CODES:
        return MODEL_CODES[key]
    return "".join(_first_alnum(w) for w in _split_words(name) if _first_alnum(w))


def supplier_abbr(name: str) -> str:
    """Look up or auto-derive a supplier code.
    'Mercis' → 'MRC'  ·  'Fabric Library' → 'FL'  (first alnum char each word)
    """
    if not name:
        return ""
    key = name.strip().lower()
    if key in SUPPLIER_CODES:
        return SUPPLIER_CODES[key]
    if re.match(r"^[A-Z]{2,5}$", name.strip()):
        return name.strip()
    return "".join(_first_alnum(w) for w in _split_words(name) if _first_alnum(w))


def color_abbr(code: str) -> str:
    """Abbreviate a supplier colour code for use in the SKU.
    '14-Vela' → '14VEL'   ·   'Beige' → 'BEI'   ·   'Natural Oak' → 'NAT'
    """
    if not code:
        return ""
    code = code.strip()
    parts = re.split(r"[-\s]+", code)
    nums  = [p for p in parts if re.match(r"^\d+$", p)]
    names = [p for p in parts if not re.match(r"^\d+$", p)]
    num_str  = "".join(nums)
    name_str = "".join(names)[:3].upper()
    return (num_str + name_str).upper()


def product_sku(mdl: str) -> str:
    """'CMR' → 'CP-CMR'"""
    return f"CP-{mdl.upper()}" if mdl else "CP"


def variant_sku(mdl: str, sup: str, color_code: str, finish: str) -> str:
    """Build the full internal variant SKU from components.
    ('CMR', 'MRC', '14-Vela', 'OAK') → 'CP-CMR-MRC-14VEL-OAK'
    """
    parts = ["CP"]
    if mdl:        parts.append(mdl.upper())
    if sup:        parts.append(sup.upper())
    if color_code: parts.append(color_abbr(color_code))
    if finish:     parts.append(finish.upper())
    return "-".join(parts) if len(parts) > 1 else ""
