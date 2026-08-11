"""
히스토리 백필 (1회 실행).

지금 CSV를 매일 덮어써서 어제 값이 없다. 하지만 yfinance로 발행일까지 소급이 된다.
한 번 돌리면
  - 차트가 첫날부터 그려지고
  - KI 터치 여부가 '미확인'에서 실제 판정으로 바뀌고
  - 종가/기준가 이상치(예: MU 249.5%)가 급점프인지 완만한 상승인지 즉시 구분된다.
    어느 날 하루에 튀었으면 액면분할, 완만히 올랐으면 진짜 상승이다.

실행:  python backfill.py
       python backfill.py --product B --force
"""

from __future__ import annotations

import argparse
from datetime import date

import config as cfg
from data_utils import fetch_history
from store import load_history, write_history


def barrier_at(product: dict, d: date):
    """d 시점에서 '다음 평가차수'의 배리어 비율."""
    for s in sorted(product["schedule"], key=lambda x: x["date"]):
        if s["date"] >= d:
            return s["barrier"]
    return None


def jump_scan(pairs, threshold: float = 0.35):
    """전일 대비 |변화율|이 임계 초과인 날. 액면분할 후보."""
    out = []
    for (d0, c0), (d1, c1) in zip(pairs, pairs[1:]):
        if c0 and abs(c1 / c0 - 1) >= threshold:
            out.append((d1, c0, c1, c1 / c0 - 1))
    return out


def main(only=None, force=False):
    today = date.today()
    products = cfg.normalized_products()
    if only:
        products = [p for p in products if p["id"] == only]

    existing = [] if force else load_history(cfg.HISTORY_PATH)
    keys = {(r["date"], r["product"], r["ticker"]) for r in existing}
    rows = list(existing)
    added = 0

    for p in products:
        start = p["issue_date"]
        end = min(today, max(s["date"] for s in p["schedule"]))
        print(f"\n■ 상품 {p['id']} · {p['name']}  ({start} ~ {end})")

        for ticker, meta in p["underlyings"].items():
            strike = float(meta["strike"])
            ki_px = strike * p["ki_barrier"]
            try:
                pairs = fetch_history(ticker, start, end)
            except Exception as e:                # noqa: BLE001
                print(f"  [FAIL] {ticker}: {e}")
                continue
            if not pairs:
                print(f"  [FAIL] {ticker}: 데이터 없음")
                continue

            n = 0
            lo = min(pairs, key=lambda x: x[1])
            for d, close in pairs:
                key = (d.strftime("%Y-%m-%d"), p["id"], ticker)
                if key in keys:
                    continue
                b = barrier_at(p, d)
                bpx = strike * b if b else None
                rows.append({
                    "date": key[0], "product": p["id"], "ticker": ticker,
                    "close": round(close, 6), "strike": strike,
                    "level_pct": round(close / strike, 6),
                    "barrier_px": round(bpx, 6) if bpx else "",
                    "buf_barrier": round(close / bpx - 1, 6) if bpx else "",
                    "ki_px": round(ki_px, 6),
                    "buf_ki": round(close / ki_px - 1, 6),
                })
                keys.add(key)
                n += 1

            touched = [d for d, c in pairs if c <= ki_px]
            jumps = jump_scan(pairs)
            print(f"  {meta['display']:<14} {n:>4}행 | "
                  f"최저 {lo[1]:,.2f} ({lo[0]}, 수준 {lo[1]/strike*100:.1f}%) | "
                  f"KI {'터치 ' + str(min(touched)) if touched else '미터치'}")
            if jumps:
                print(f"    ⚠️ 급변동 {len(jumps)}건 — 액면분할/병합 의심:")
                for d, c0, c1, r in jumps[:5]:
                    print(f"       {d}  {c0:,.2f} → {c1:,.2f}  ({r*100:+.1f}%)")
            added += n

    write_history(cfg.HISTORY_PATH, rows)
    print(f"\n총 {added}행 추가 · {cfg.HISTORY_PATH} 에 {len(rows)}행")
    print("이제 main.py를 돌리면 KI 터치와 추이 차트가 정상 표시된다.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", default=None)
    ap.add_argument("--force", action="store_true", help="기존 history 무시하고 전면 재작성")
    args = ap.parse_args()
    main(args.product, args.force)
