"""
ELS early-redemption monitor - main pipeline.

    fetch -> compute -> append history -> chart -> AI comment -> mail -> export

This is a fixed workflow, not an agent. Same order every day is what makes
yesterday's email reproducible and traceable.

    python main.py            fetch + send
    python main.py --dry-run  no mail, just write preview.html
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

import config as cfg
from ai_comment import log_comment, make_comment
from chart_utils import buffer_chart, save_png
from compute import (KI_HIT, ProductView, evaluate, preheader, summarize,
                     to_history_rows)
from data_utils import fetch_quote
from email_utils import new_cid, send_email
from render import render_html, render_text
from store import append_history, load_history, load_state, save_state


def collect(tickers):
    quotes = {}
    for t in tickers:
        q = fetch_quote(t)
        quotes[t] = q
        mark = "ok" if q.ok else "FAIL"
        print(f"  [{mark:4}] {t:8} {q.price if q.ok else q.error}  obs={q.obs_date}")
    return quotes


def export_dashboard(views, summary, comment, today):
    """Static data for the GitHub Pages dashboard."""
    os.makedirs(cfg.DOCS_DATA, exist_ok=True)

    if os.path.exists(cfg.HISTORY_PATH):
        with open(cfg.HISTORY_PATH, "r", encoding="utf-8-sig") as src, \
             open(os.path.join(cfg.DOCS_DATA, "history.csv"), "w", encoding="utf-8") as dst:
            dst.write(src.read())

    payload = {
        "generated": str(today),
        "summary": summary,
        "comment": comment,
        "products": [{
            "id": v.id, "name": v.name, "status": v.status, "label": v.label,
            "icon": v.icon, "eval_no": v.eval_no,
            "eval_date": str(v.eval_date) if v.eval_date else None,
            "dday": v.dday, "barrier": v.barrier, "coupon_cum": v.coupon_cum,
            "payout": v.payout, "principal": v.principal, "is_final": v.is_final,
            "ki_ratio": next((l.ki_px / l.strike for l in v.legs if l.ki_px), None),
            "warnings": v.warnings,
            "legs": [{
                "ticker": l.ticker, "display": l.display, "strike": l.strike,
                "close": l.quote.price, "obs_date": str(l.quote.obs_date) if l.quote.obs_date else None,
                "level_pct": l.level_pct, "buf_barrier": l.buf_barrier,
                "buf_ki": l.buf_ki, "need_up": l.need_up,
                "barrier_px": l.barrier_px, "ki_px": l.ki_px,
                "is_worst": l.is_worst, "ki_touched": l.ki.get("touched"),
                "ki_observed": l.ki.get("observed"), "ki_min_level": l.ki.get("min_level"),
                "warn": l.warn, "error": l.quote.error,
            } for l in v.legs],
        } for v in views],
    }
    with open(os.path.join(cfg.DOCS_DATA, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"  대시보드 데이터 내보냄 -> {cfg.DOCS_DATA}")


def detect_changes(views, state: dict) -> list[str]:
    """Day-over-day status changes. Basis for a separate immediate alert."""
    events = []
    for v in views:
        prev = state.get(v.id, {})
        if prev.get("status") and prev["status"] != v.status:
            events.append(f"[{v.id}] 상태 변화: {prev['status']} → {v.status}")
        if v.status == KI_HIT and prev.get("status") != KI_HIT:
            events.append(f"[{v.id}] KI 터치 발생")
        if v.dday in cfg.THRESHOLDS["dday_alert"] and prev.get("dday") != v.dday:
            events.append(f"[{v.id}] 평가일 D-{v.dday}")
    return events


def job(dry_run: bool = False) -> int:
    today = date.today()
    products = cfg.normalized_products()

    print(f"■ ELS 모니터 {today}")

    issues = cfg.validate()
    for m in issues:
        print(f"  ⚠️ {m}")

    print("· 시세 수집")
    quotes = collect(cfg.all_tickers())

    history = load_history(cfg.HISTORY_PATH)
    if not history:
        print("  ! history.csv 없음 — KI 터치 판정이 '미확인'으로 나온다. "
              "backfill.py를 1회 실행할 것")

    print("· 상품 평가")
    views: list[ProductView] = []
    for p in products:
        try:
            v = evaluate(p, quotes, history, cfg.THRESHOLDS, today)
        except Exception as e:                    # noqa: BLE001
            print(f"  [FAIL] 상품 {p['id']} 평가 실패: {e}")
            continue
        views.append(v)
        print(f"  [{v.id}] {v.label}"
              f"{f' · worst {v.worst.display} {v.worst.buf_barrier*100:+.2f}%' if v.worst and v.worst.buf_barrier is not None else ''}"
              f"{f' · D-{v.dday}' if v.dday is not None else ''}")

    if not views:
        print("! 평가 가능한 상품이 없다. 중단")
        return 1

    rows = []
    for v in views:
        rows += to_history_rows(v, today)
    n = append_history(cfg.HISTORY_PATH, rows)
    print(f"· history 적재 {n}행 (총 {len(history)+n}행)")
    history = load_history(cfg.HISTORY_PATH)

    for m in issues:
        if "ANTHROPIC_API_KEY" not in m and views:
            views[0].warnings.append(f"설정: {m}")

    summary = summarize(views)
    pre = preheader(views, summary)
    print(f"· 요약: {pre}")

    events = detect_changes(views, load_state(cfg.STATE_PATH))
    for e in events:
        print(f"  ▲ {e}")
    save_state(cfg.STATE_PATH,
               {v.id: {"status": v.status, "dday": v.dday, "date": str(today)} for v in views})

    print("· 차트")
    png = None
    try:
        png = buffer_chart(views, history)
        if png:
            save_png(png, os.path.join(cfg.DOCS_DATA, "buffer.png"))
            print(f"  생성 {len(png):,} bytes")
        else:
            print("  건너뜀 (시계열 2개 미만 — 백필 필요)")
    except Exception as e:                        # noqa: BLE001
        print(f"  [FAIL] 차트 생성 실패, 계속 진행: {e}")

    print("· AI 코멘트")
    comment = make_comment(views, cfg.AI_CONFIG, today)
    log_comment(os.path.join(cfg.BASE_DIR, "data", "comments.jsonl"), today, comment)
    print(f"  {(comment or '(비활성)')[:80]}")

    cid = new_cid() if png else None
    html = render_html(views, summary, pre, comment, cid, cfg.DASHBOARD_URL, today)
    text = render_text(views, summary, pre, comment, today)

    export_dashboard(views, summary, comment, today)

    subject = f"ELS Report ({today:%Y-%m-%d})"

    if dry_run:
        out = os.path.join(cfg.BASE_DIR, "preview.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"· [dry-run] 메일 미전송. 미리보기 -> {out}")
        return 0

    print("· 메일")
    send_email(subject=subject, html=html, text=text, config=cfg.EMAIL_CONFIG,
               inline_images={cid: png} if png else None)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="메일 전송 없이 preview.html만 생성")
    args = ap.parse_args()
    sys.exit(job(dry_run=args.dry_run))
