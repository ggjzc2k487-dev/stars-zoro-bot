from __future__ import annotations

import hashlib
import html
import re


def esc(text: str) -> str:
    return html.escape(text or "", quote=False)


def fmt_number(value: float) -> str:
    """12345.6 -> '12 345,60'; маленькие числа показываем точнее."""
    if value >= 100:
        s = f"{value:,.2f}"
    elif value >= 1:
        s = f"{value:,.3f}"
    else:
        s = f"{value:.6f}".rstrip("0").rstrip(".")
        if not s:
            s = "0"
    return s.replace(",", " ").replace(".", ",")


def fmt_change(pct: float | None) -> str:
    if pct is None:
        return ""
    arrow = "📈" if pct >= 0 else "📉"
    sign = "+" if pct >= 0 else ""
    return f"{arrow} {sign}{pct:.2f}% за 24ч".replace(".", ",")


CURRENCY_SYMBOLS = {"usd": "$", "rub": "₽", "eur": "€"}


def fmt_money(value: float, currency: str) -> str:
    symbol = CURRENCY_SYMBOLS.get(currency.lower(), currency.upper())
    if symbol == "$":
        return f"${fmt_number(value)}"
    return f"{fmt_number(value)} {symbol}"


def normalize_title(title: str) -> str:
    """Для дедупликации: убираем источник в конце, регистр, пунктуацию."""
    title = re.sub(r"\s+[-–—|]\s+[^-–—|]{2,40}$", "", title)
    title = re.sub(r"[^\w\s]", "", title.lower())
    return re.sub(r"\s+", " ", title).strip()


def make_key(prefix: str, text: str) -> str:
    return f"{prefix}:{hashlib.sha1(text.encode('utf-8')).hexdigest()[:16]}"
