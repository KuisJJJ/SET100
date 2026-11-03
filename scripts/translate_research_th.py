#!/usr/bin/env python3
"""Normalize user-facing SET100 research text to Thai.

This is a display-layer normalization step. It leaves structural enums, numeric fields,
valuation logic and update-status logic unchanged. Translations are cached by SHA256 of
the original text so future workflow runs are deterministic and fast.
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
    "summary", "debtEbitdaBasis", "debtEbitdaNote", "thesis", "bear",
    "marketBelieves", "marketMissing", "variables", "fit", "moatReason",
    "industryComparison",
]
TECH_TERMS = [
    "SET100", "SETTRADE", "SET", "IR", "P/E", "P/BV", "EV/EBITDA", "EBITDA",
    "EBIT", "NPAT", "EPS", "FCF", "OCF", "ROE", "ROIC", "D/E", "NIM", "NPL",
    "CAGR", "TAM", "SAM", "SOM", "YoY", "QoQ", "AI", "FX", "CAPEX", "SG&A",
    "ASP", "SSSG", "RevPAR", "ADR", "RASK", "CASK", "BOED", "PPA", "COD",
    "FID", "NAV", "IRR", "ECL", "LTV", "GPM", "GWh", "MW", "GW", "THB", "USD"
]
THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
LATIN_RE = re.compile(r"[A-Za-z]")
MARKER_RE = re.compile(r"ZXQSEG(\d{6})QXZ", re.I)


def needs_translation(text: Any) -> bool:
    if not isinstance(text, str):
        return False
    s = text.strip()
    if len(s) < 3:
        return False
    thai = len(THAI_RE.findall(s))
    latin = len(LATIN_RE.findall(s))
    return latin >= 18 and (thai < 8 or latin > thai * 2.2)


def protect_terms(text: str) -> tuple[str, dict[str, str]]:
    protected: dict[str, str] = {}
    out = text
    for idx, term in enumerate(sorted(TECH_TERMS, key=len, reverse=True)):
        token = f"ZZZTERM{idx}ZZZ"
        if term in out:
            out = out.replace(term, token)
            protected[token] = term
    return out, protected


def restore_terms(text: str, protected: dict[str, str]) -> str:
    out = text
    for token, term in protected.items():
        out = out.replace(token, term)
        out = out.replace(" ".join(token), term)
    return out


def cache_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def google_translate(text: str) -> str:
    data = urllib.parse.urlencode({
        "client": "gtx", "sl": "auto", "tl": "th", "dt": "t", "q": text,
    }).encode("utf-8")
    url = "https://translate.googleapis.com/translate_a/single"
    last_error = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url, data=data,
                headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            translated = "".join(part[0] for part in payload[0] if part and part[0]).strip()
            if not translated:
                raise RuntimeError("empty translation")
            return translated
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(0.8 + attempt * 1.2)
    raise RuntimeError(str(last_error))


def translate_one(text: str) -> str:
    protected_text, protected = protect_terms(text)
    return restore_terms(google_translate(protected_text), protected).strip()


def make_batches(items: list[tuple[str, str]], max_chars: int = 2800) -> list[list[tuple[str, str]]]:
    batches: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    size = 0
    for item in items:
        add = len(item[1]) + 30
        if current and size + add > max_chars:
            batches.append(current)
            current = []
            size = 0
        current.append(item)
        size += add
    if current:
        batches.append(current)
    return batches


def translate_batch(batch: list[tuple[str, str]]) -> dict[str, str]:
    protected_all: dict[str, str] = {}
    pieces: list[str] = []
    for idx, (_key, text) in enumerate(batch):
        protected, mapping = protect_terms(text)
        protected_all.update(mapping)
        pieces.append(f"ZXQSEG{idx:06d}QXZ\n{protected}")
    joined = "\n".join(pieces)
    translated = restore_terms(google_translate(joined), protected_all)

    matches = list(MARKER_RE.finditer(translated))
    if len(matches) != len(batch):
        # Safe fallback: only this small batch is retried individually.
        out: dict[str, str] = {}
        for key, text in batch:
            out[key] = translate_one(text)
        return out

    out: dict[str, str] = {}
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(translated)
        segment = translated[start:end].strip(" \n:-")
        out[batch[idx][0]] = segment
    return out


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def gather_targets(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
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
        for idx, value in enumerate(stock.get("flags") or []):
            if needs_translation(value):
                targets.append((ticker, f"flags::{idx}", value))
        for idx, src in enumerate(stock.get("sources") or []):
            label = src.get("label") if isinstance(src, dict) else None
            if needs_translation(label):
                targets.append((ticker, f"sources::{idx}::label", label))
    return targets


def set_value(stock: dict[str, Any], path: str, translated: str) -> None:
    if path.startswith("framework::"):
        stock.setdefault("framework", {})[path.split("::", 1)[1]] = translated
    elif path.startswith("flags::"):
        stock.setdefault("flags", [])[int(path.split("::")[1])] = translated
    elif path.startswith("sources::"):
        parts = path.split("::")
        stock.setdefault("sources", [])[int(parts[1])]["label"] = translated
    else:
        stock[path] = translated


def main() -> None:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    cache: dict[str, str] = load_json(CACHE, {})
    targets = gather_targets(payload)

    originals: dict[str, str] = {}
    for _, _, text in targets:
        key = cache_key(text)
        if key not in cache:
            originals[key] = text

    failures: dict[str, str] = {}
    if originals:
        batches = make_batches(list(originals.items()))
        print(f"Thai normalization: {len(originals)} new text blocks in {len(batches)} batches")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            future_map = {pool.submit(translate_batch, batch): batch for batch in batches}
            done = 0
            for future in concurrent.futures.as_completed(future_map):
                batch = future_map[future]
                try:
                    cache.update(future.result())
                except Exception as exc:  # noqa: BLE001
                    # Final fallback for a failed batch: retry individually, keeping failures isolated.
                    for key, text in batch:
                        try:
                            cache[key] = translate_one(text)
                        except Exception as inner:  # noqa: BLE001
                            failures[key] = f"{type(inner).__name__}: {inner}"
                done += 1
                if done % 10 == 0 or done == len(batches):
                    print(f"  translated batches {done}/{len(batches)}")

    by_ticker = {s.get("ticker"): s for s in payload.get("stocks", [])}
    applied = 0
    for ticker, path, original in targets:
        translated = cache.get(cache_key(original))
        if translated:
            set_value(by_ticker[ticker], path, translated)
            applied += 1

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
        "targetBlocksDetected": len(targets),
        "newTranslationsAttempted": len(originals),
        "cacheSize": len(cache),
        "applied": applied,
        "requestFailures": len(failures),
        "remainingEnglishHeavyBlocks": len(remaining_rows),
        "remaining": remaining_rows[:1000],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Thai normalization applied: {applied}")
    print(f"Translation request failures: {len(failures)}")
    print(f"Remaining English-heavy blocks: {len(remaining_rows)}")


if __name__ == "__main__":
    main()
