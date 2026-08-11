"""
데모 프리뷰 — 네트워크도 SMTP도 없이 결과물을 눈으로 확인한다.

실제 종가는 고정값으로 넣고, 히스토리는 합성으로 만든다.
산출물은 전부 _demo/ 아래에만 쓴다 (data/, docs/ 를 오염시키지 않는다).

  python demo_preview.py
  → _demo/mail.html      메일 본문 (브라우저로 열면 보인다)
  → _demo/index.html     대시보드
  → _demo/buffer.png     차트
"""
from __future__ import annotations

import json
import os
import random
import shutil
from datetime import date, timedelta

import config as cfg

DEMO = os.path.join(cfg.BASE_DIR, "_demo")
os.makedirs(os.path.join(DEMO, "data"), exist_ok=True)

TODAY = date(2026, 8, 11)
LAST = {"^N225": 66970.22, "^GSPC": 7753.11, "^KS200": 977.84,
        "PLTR": 175.23, "MU": 861.00}
OBS = {t: date(2026, 8, 10) for t in LAST}

random.seed(7)


def synth(p):
    rows = []
    for t, meta in p["underlyings"].items():
        strike, ki = meta["strike"], meta["strike"] * p["ki_barrier"]
        end, n = LAST[t], (TODAY - p["issue_date"]).days
        for i in range(n):
            d = p["issue_date"] + timedelta(days=i)
            if d.weekday() >= 5:
                continue
            f = i / max(n - 1, 1)
            c = max(strike + (end - strike) * (f ** 1.15) * (1 + random.gauss(0, .007)), .01)
            b = next((s["barrier"] for s in p["schedule"] if s["date"] >= d), None)
            bpx = strike * b if b else None
            rows.append({"date": d.strftime("%Y-%m-%d"), "product": p["id"], "ticker": t,
                         "close": round(c, 4), "strike": strike,
                         "level_pct": round(c / strike, 6),
                         "barrier_px": round(bpx, 4) if bpx else "",
                         "buf_barrier": round(c / bpx - 1, 6) if bpx else "",
                         "ki_px": round(ki, 4), "buf_ki": round(c / ki - 1, 6)})
    return rows


def main():
    from chart_utils import buffer_chart, save_png, setup_font
    from compute import evaluate, preheader, summarize
    from data_utils import Quote
    from render import render_html, render_text
    from store import load_history, write_history

    hist_path = os.path.join(DEMO, "data", "history.csv")
    products = cfg.normalized_products()
    write_history(hist_path, [r for p in products for r in synth(p)])
    history = load_history(hist_path)

    quotes = {t: Quote(t, price=LAST[t], obs_date=OBS[t]) for t in LAST}
    views = [evaluate(p, quotes, history, cfg.THRESHOLDS, TODAY) for p in products]
    s = summarize(views)
    pre = preheader(views, s)

    print(f"합성 히스토리 {len(history)}행")
    print(f"프리헤더: {pre}\n")
    print(render_text(views, s, pre, None, TODAY))

    print(f"한글 폰트: {'탐지됨' if setup_font() else '없음 — 영문 폴백'}")
    png = buffer_chart(views, history)
    if png:
        save_png(png, os.path.join(DEMO, "buffer.png"))
        save_png(png, os.path.join(DEMO, "data", "buffer.png"))

    comment = ("상품 A는 worst-of KOSPI200이 배리어를 크게 밑돌아 1차 조기상환 가능성이 "
               "사실상 소멸한 상태임. 잔여 기간 내 요구 회복 폭이 커 2차 이월을 전제로 볼 필요가 있음.\n"
               "상품 B는 worst-of 팔란티어가 배리어 위 여유를 유지 중이나, "
               "마이크론 기준가 정합성 확인이 선행되어야 함. (※ 데모용 고정 문구)")

    html = render_html(views, s, pre, comment, None,
                       "https://example.github.io/els/", TODAY)
    with open(os.path.join(DEMO, "mail.html"), "w", encoding="utf-8") as f:
        f.write(html)

    shutil.copy(os.path.join(cfg.DOCS_DIR, "index.html"), os.path.join(DEMO, "index.html"))
    payload = {"generated": str(TODAY), "summary": s, "comment": comment,
               "products": [{
                   "id": v.id, "name": v.name, "status": v.status, "label": v.label,
                   "icon": v.icon, "eval_no": v.eval_no, "eval_date": str(v.eval_date),
                   "dday": v.dday, "barrier": v.barrier, "coupon_cum": v.coupon_cum,
                   "payout": v.payout, "principal": v.principal, "is_final": v.is_final,
                   "warnings": v.warnings,
                   "legs": [{"ticker": l.ticker, "display": l.display, "strike": l.strike,
                             "close": l.quote.price, "obs_date": str(l.quote.obs_date),
                             "level_pct": l.level_pct, "buf_barrier": l.buf_barrier,
                             "buf_ki": l.buf_ki, "need_up": l.need_up,
                             "is_worst": l.is_worst, "ki_touched": l.ki.get("touched"),
                             "ki_observed": l.ki.get("observed"),
                             "ki_min_level": l.ki.get("min_level"),
                             "warn": l.warn, "error": l.quote.error} for l in v.legs],
               } for v in views]}
    with open(os.path.join(DEMO, "data", "summary.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n산출:\n  {DEMO}/mail.html\n  {DEMO}/index.html\n  {DEMO}/buffer.png")
    print("대시보드는 fetch를 쓰므로 로컬 서버로 열 것:")
    print(f"  python -m http.server -d {DEMO} 8000   →  http://localhost:8000")


if __name__ == "__main__":
    main()
