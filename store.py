"""
history.csv : append-only 시계열 저장소.

이 파일 하나가 표 / 차트 / KI 터치 판정 / AI 코멘트의 단일 소스다.
매일 덮어쓰던 els_report.csv를 대체한다.

컬럼
  date        관측일(YYYY-MM-DD) — 실행일이 아니라 '그 종가가 형성된 날'
  product     상품 id
  ticker      기초자산
  close       종가
  strike      기준가격
  level_pct   close / strike
  barrier_px  해당 시점 다음 평가차수의 조기상환 기준가
  buf_barrier close / barrier_px - 1   (+ = 배리어 위, 상환권)
  ki_px       KI 가격
  buf_ki      close / ki_px - 1        (+ = KI 위, 안전)
"""

from __future__ import annotations

import csv
import json
import os
from datetime import date, datetime
from typing import Iterable

FIELDS = [
    "date", "product", "ticker", "close", "strike", "level_pct",
    "barrier_px", "buf_barrier", "ki_px", "buf_ki",
]


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def load_history(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("close", "strike", "level_pct", "barrier_px",
                  "buf_barrier", "ki_px", "buf_ki"):
            try:
                r[k] = float(r[k])
            except (TypeError, ValueError):
                r[k] = None
    return rows


def write_history(path: str, rows: Iterable[dict]) -> None:
    """전체 재작성. 백필 전용."""
    _ensure_dir(path)
    rows = sorted(rows, key=lambda r: (r["date"], r["product"], r["ticker"]))
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def append_history(path: str, rows: Iterable[dict]) -> int:
    """
    같은 (date, product, ticker) 키가 이미 있으면 건너뛴다.
    휴장일에 두 번 돌려도 중복이 쌓이지 않는다.
    """
    rows = list(rows)
    if not rows:
        return 0

    existing = load_history(path)
    keys = {(r["date"], r["product"], r["ticker"]) for r in existing}
    fresh = [r for r in rows if (r["date"], r["product"], r["ticker"]) not in keys]
    if not fresh:
        return 0

    _ensure_dir(path)
    new_file = not os.path.exists(path)
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        for r in fresh:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    return len(fresh)


# ── KI 터치 판정 ────────────────────────────────────────────────
def ki_touch(history: list[dict], product_id: str, ticker: str) -> dict:
    """
    발행 이후 종가가 KI를 하회한 적이 있는지.
    반환: {"touched": bool, "date": str|None, "min_close": float|None,
           "min_level": float|None, "observed": bool}
    observed=False 는 히스토리가 없어 판정 불가라는 뜻 (= '미확인').
    """
    rows = [r for r in history
            if r["product"] == product_id and r["ticker"] == ticker
            and r["close"] is not None and r["ki_px"]]
    if not rows:
        return {"touched": False, "date": None, "min_close": None,
                "min_level": None, "observed": False}

    lo = min(rows, key=lambda r: r["close"])
    hit = [r for r in rows if r["close"] <= r["ki_px"]]
    return {
        "touched": bool(hit),
        "date": min(h["date"] for h in hit) if hit else None,
        "min_close": lo["close"],
        "min_level": (lo["close"] / lo["strike"]) if lo["strike"] else None,
        "observed": True,
    }


def series(history: list[dict], product_id: str, ticker: str, field: str = "buf_barrier"):
    rows = sorted(
        (r for r in history if r["product"] == product_id and r["ticker"] == ticker),
        key=lambda r: r["date"],
    )
    return [(r["date"], r[field]) for r in rows if r.get(field) is not None]


# ── 상태 저장 (변화 감지용) ─────────────────────────────────────
def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(path: str, state: dict) -> None:
    _ensure_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, default=str)


def today_str() -> str:
    return date.today().strftime("%Y-%m-%d")


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()
