#!/usr/bin/env python3
"""Normalize all user-facing SET100 research text to Thai.

Design goals:
- Keep structural/schema fields (ticker, valuation enums, update statuses, numbers) unchanged.
- Translate only English-heavy user-facing research fields.
- Cache translations by SHA256(original text) so future runs are fast and deterministic.
- Never fail the whole dashboard build because one translation request failed; unresolved items
  are reported in research_translation_status.json and retried on the next run.

Translation transport uses Google's public translate endpoint from the GitHub Actions runner.
The research repository is public, but the cache is committed so repeated runs do not resend
already translated text.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data.json"
CACHE = ROOT / "research_th_cache.json"
STATUS = ROOT / "research_translation_status.json"

TARGET_FIELDS = [
    "summary",
    "debtEbitdaBasis",
    "debtEbitdaNote",
    "thesis",
    "bear",
    "marketBelieves",
    "marketMissing",
    "variables",
    "fit",
    "moatReason",
    "industryComparison",
]

TECH_TERMS = [
    "SET100", "SET", "SETTRADE", "IR", "P/E", "P/BV", "EV/EBITDA", "EBITDA",
    "EBIT", "NPAT", "EPS", "FCF", "OCF", "ROE", "ROIC", "D/E", "NIM", "NPL",
    "CAGR", "TAM", "SAM", "SOM", "YoY", "QoQ", "AI", "FX", "CAPEX", "SG&A",
    "ASP", "SSSG", "RevPAR", "ADR", "RASK", "CASK", "BOED", "PPA", "COD",
    "FID", "NAV", "IRR", "ECL", "LTV", "GPM", "GWh", "MW", "GW", "THB", "USD"
]

THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
LATIN_RE = re.compile(r"[A-Za-z]")


def needs_translation(text: Any) -> bool:
    if not isinstance(text, str):
        return False
    s = text.strip()
    if len(s) < 3:
        return False
    thai = len(THAI_RE.findall(s))
    latin = len(LATIN_RE.findall(s))
    # Translate English-heavy text, while leaving Thai paragraphs that merely contain
    # English financial acronyms untouched.
    return latin >= 18 and (thai < 8 or latin > thai * 2.2)


def protect_terms(text: str) -> tuple[str, dict[str, str]]:
    protected = {}
    out = text
    # Longest terms first so EV/EBITDA wins before EBITDA, etc.
    for idx, term in enumerate(sorted(TECH_TERMS, key=len, reverse=True)):
        token = f"ZZZTERM{idx}ZZZ"
        if term in out:
            out = out.replace(term, token)
            protected[token] = term
    return out, protected


def restore_terms(text: str, protected: dict[str, str]) -> str:
    out = text
    for token, term in protected.items():
        # Google occasionally inserts spaces inside a synthetic token; accept both.
        out = out.replace(token, term)
        spaced = " ".join(token)
        out = out.replace(spaced, term)
    return out


def cache_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def translate_one(text: str) -> str:
    protected_text, protected = protect_terms(text)
    query = urllib.parse.urlencode({
        "client": "gtx",
        "sl": "auto",
        "tl": "th",
        "dt": "t",
        "q": protected_text,
    })
    url = "https://translate.googleapis.com/translate_a/single?" + query
    last_error = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            translated = "".join(part[0] for part in payload[0] if part and part[0])
            translated = restore_terms(translated, protected).strip()
            if not translated:
                raise RuntimeError("empty translation")
            return translated
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(1.0 + attempt * 1.5)
    raise RuntimeError(str(last_error))


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def gather_targets(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return (ticker, logical_path, original_text)."""
    targets: list[tuple[str, str, str]] = []
    for stock in payload.get("stocks", []):
        ticker = stock.get("ticker", "?")
        for field in TARGET_FIELDS:
            value = stock.get(field)
            if needs_translation(value):
                targets.append((ticker, field, value))
        for key, value in (stock.get("framework") or {}).items():
            if needs_translation(value):
                targets.append((ticker, f"framework::{key}", value))
        flags = stock.get("flags") or []
        for idx, value in enumerate(flags):
            if needs_translation(value):
                targets.append((ticker, f"flags::{idx}", value))
        for idx, src in enumerate(stock.get("sources") or []):
            label = src.get("label") if isinstance(src, dict) else None
            if needs_translation(label):
                targets.append((ticker, f"sources::{idx}::label", label))
    return targets


def set_value(stock: dict[str, Any], path: str, translated: str) -> None:
    if path.startswith("framework::"):
        key = path.split("::", 1)[1]
        stock.setdefault("framework", {})[key] = translated
        return
    if path.startswith("flags::"):
        idx = int(path.split("::")[1])
        stock.setdefault("flags", [])[idx] = translated
        return
    if path.startswith("sources::"):
        parts = path.split("::")
        idx = int(parts[1])
        stock.setdefault("sources", [])[idx]["label"] = translated
        return
    stock[path] = translated


def main() -> None:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    cache: dict[str, str] = load_json(CACHE, {})
    targets = gather_targets(payload)

    # Unique original strings only; identical text is translated once.
    originals: dict[str, str] = {}
    for _, _, text in targets:
        key = cache_key(text)
        if key not in cache:
            originals[key] = text

    failures: dict[str, str] = {}
    if originals:
        print(f"Thai normalization: {len(originals)} new English-heavy text blocks")
        # Conservative concurrency reduces rate-limit risk while keeping the workflow practical.
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            future_map = {pool.submit(translate_one, text): (key, text) for key, text in originals.items()}
            for count, future in enumerate(concurrent.futures.as_completed(future_map), 1):
                key, text = future_map[future]
                try:
                    cache[key] = future.result()
                except Exception as exc:  # noqa: BLE001
                    failures[key] = f"{type(exc).__name__}: {exc}"
                if count % 50 == 0:
                    print(f"  processed {count}/{len(originals)}")

    by_ticker = {s.get("ticker"): s for s in payload.get("stocks", [])}
    applied = 0
    unresolved: list[dict[str, str]] = []
    for ticker, path, original in targets:
        key = cache_key(original)
        translated = cache.get(key)
        if translated:
            set_value(by_ticker[ticker], path, translated)
            applied += 1
        else:
            unresolved.append({"ticker": ticker, "field": path, "sample": original[:180]})

    # Final QA after applying cached/new translations.
    remaining = gather_targets(payload)
    remaining_rows = [
        {"ticker": t, "field": p, "sample": txt[:180]}
        for t, p, txt in remaining
    ]

    payload.setdefault("meta", {})["language"] = "th"
    payload["meta"]["thaiResearchNormalization"] = {
        "enabled": True,
        "translatedBlocksApplied": applied,
        "remainingEnglishHeavyBlocks": len(remaining_rows),
    }

    DATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    STATUS.write_text(json.dumps({
        "targetLanguage": "th",
        "targetBlocks": len(targets),
        "newTranslationsAttempted": len(originals),
        "cacheSize": len(cache),
        "applied": applied,
        "requestFailures": len(failures),
        "remainingEnglishHeavyBlocks": len(remaining_rows),
        "remaining": remaining_rows[:500],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Thai normalization applied: {applied}")
    print(f"Translation request failures: {len(failures)}")
    print(f"Remaining English-heavy blocks: {len(remaining_rows)}")


if __name__ == "__main__":
    main()
