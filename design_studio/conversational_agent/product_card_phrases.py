"""Shared regex patterns for product-card style phrases.

Consumed by ``direct_style.py`` (global NL rules), ``element_focused_style.py``
(focused catalog/showcase cards), and ``product_card_requests.py`` (complaint-driven fixes).
"""

from __future__ import annotations

import re

PRODUCT_CARD_BORDER_RADIUS_ZERO = re.compile(
    r"\b(?:product|card)s?\b.{0,40}\bborder\s*-?\s*radius\b.{0,20}\b0\b"
    r"|\b(?:product|card)s?\b.{0,30}\b(?:no|zero)\s+(?:border\s*)?radius\b",
    re.I,
)

ELEMENT_BORDER_RADIUS_ZERO = re.compile(
    r"\bborder\s*-?\s*radius\s*(?:to\s+)?0\b"
    r"|\bno\s+(?:border\s*)?radius\b"
    r"|\bsquare\s+corners?\b"
    r"|\bsharp\s+corners?\b",
    re.I,
)

PRODUCT_CARD_RECTANGLE = re.compile(
    r"\brectangle|rectangular|square\s+(product\s+)?cards?\b"
    r"|\bproduct\s+cards?\s+.{0,30}rectangle\b",
    re.I,
)

PRODUCT_SECTION_RE = re.compile(
    r"\bproduct\s+cards?\b"
    r"|\b(?:our\s+)?products?\s+(?:section|cards?|grid)\b"
    r"|\ball\s+products?\s*(?:&\s*services)?\b"
    r"|\bproducts?\s*&\s*services\b"
    r"|\b(?:under|in)\s+(?:the\s+)?all\s+products\b",
    re.I,
)

WANTS_RECTANGLE_RE = re.compile(
    r"\brectangle|rectangular|square\s+cards?\b"
    r"|\bnot\s+(?:round|circular|circle|oval)\b"
    r"|\b(?:stop|no)\s+(?:round|circle|circular|oval)\b"
    r"|\boval\b|\bcircular\b|\bcircle\s+images?\b",
    re.I,
)

CARD_QUALITY_RE = re.compile(
    r"\b(?:bad|ugly|terrible|awful|horrible|wrong|broken|not\s+looking\s+good)\b"
    r"|\b(?:hide|hidden|can'?t\s+see|hard\s+to\s+read)\b"
    r"|\binformation\s+is\s+hidden\b"
    r"|\bvery\s+bad\b",
    re.I,
)

LIST_LAYOUT_RE = re.compile(
    r"\blist\s+(?:layout|view)\b|\bshow\s+more\s+(?:info|information|details)\b",
    re.I,
)
