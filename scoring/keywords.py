"""Keyword lists for CaptiveAire opportunity scoring, grouped into tiers by
how directly they signal a kitchen-ventilation / commercial-kitchen-
mechanical opportunity. This is plain keyword matching (no LLM) — the LLM,
per the project's requirements, is reserved for an optional later pass
(e.g. summarizing/classifying ambiguous descriptions), not for this core
scoring step.

TIER_A: Directly names CaptiveAire's core scope of work (hoods, grease
duct, MAU, fire suppression, walk-ins). A single hit here is a very strong
signal on its own.

TIER_B: Names the *type of venue* that generates this scope of work
(restaurant, commercial kitchen, grocery, school kitchen, etc.) even if the
permit text doesn't mention equipment specifically. Also includes shell/
core-and-shell building permits for retail or restaurant pad sites — the
kitchen isn't in yet, but a shell permit is a reliable early signal that a
tenant build-out (and CaptiveAire scope) will follow.

TIER_C: General HVAC/mechanical terms. Weak signal alone (a lot of
permits mention "mechanical" or "HVAC" with zero foodservice relevance),
but meaningful in combination with a Tier A/B hit.
"""
from __future__ import annotations

TIER_A_KEYWORDS = [
    "type i hood", "type ii hood", "type 1 hood", "type 2 hood",
    "kitchen hood", "grease hood", "hood system",
    "grease duct", "grease exhaust",
    "exhaust fan",
    "makeup air", "makeup air unit", "mau",
    "doas",
    "fire suppression", "ansul",
    "walk-in cooler", "walk-in freezer", "walk in cooler", "walk in freezer",
]

TIER_B_KEYWORDS = [
    "restaurant", "commercial kitchen", "kitchen renovation",
    "tenant build-out", "tenant buildout", "build-out", "buildout",
    "food service", "foodservice",
    "grocery", "supermarket", "bakery", "cafeteria",
    "school kitchen", "hotel kitchen", "cooking equipment",
    "food hall", "concession", "brewery", "bar", "café", "cafe",
    "coffee shop",
    # Shell/core-and-shell building permits: the building itself has no
    # kitchen yet, but a shell permit for a retail/restaurant pad site is a
    # strong leading indicator that a tenant build-out (and CaptiveAire
    # scope) follows within months. Deliberately specific phrases, not bare
    # "shell", to avoid false positives like "seashell"/"shellfish".
    "shell building", "core and shell", "core & shell", "commercial shell",
    "shell only", "shell construction", "warm shell", "cold shell",
    "white box", "vanilla shell", "shell permit", "restaurant shell",
    "retail shell",
]

TIER_C_KEYWORDS = [
    "hvac", "mechanical", "rooftop unit", "rtu",
]

# Signals that a permit is describing new construction vs. a renovation.
# Both are relevant to CaptiveAire (new build = new system; renovation =
# likely hood/equipment replacement) — used only to confirm the permit has
# a clear "project nature" signal, not to favor one over the other.
PROJECT_NATURE_KEYWORDS = [
    "new construction", "renovation", "remodel", "alteration",
    "build-out", "buildout", "addition", "interior finish",
    "shell building", "fit-out", "fit out",
]

# Occupancy/type strings across the connectors that indicate a commercial
# (non-residential) record. Checked against permit_type/permit_subtype.
COMMERCIAL_INDICATORS = [
    "commercial", "comm ", "comm.", "retail", "restaurant", "hotel",
    "office", "industrial", "medical", "institutional", "mercantile",
    "assembly", "educational", "business",
]


def find_matches(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw in text_lower]
