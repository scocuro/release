"""
상품 단위 평가.

원본 코드에서 고친 것
  1) `d > today`      -> `d >= today`   평가일 당일에 그 차수를 건너뛰던 버그
  2) `if not upcoming` -> `is None`      차수 0이 falsy로 걸리던 버그
  3) dict 삽입순서 의존 next() -> 날짜 정렬 후 선택
  4) 만기 경과 상품을 `continue`로 조용히 없애던 것 -> 'matured' 상태로 남김
  5) `decline < 0` -> "해당없음"  ->  부호 있는 실제 값 유지
     (MU가 +149%라는 정보가 통째로 날아가고 CSV 숫자 컬럼도 오염됐다)

부호 규약 (전 파일 공통, 하나만 쓴다)
  여유율 = 종가 / 기준선 - 1
    +  기준선 위 = 좋음
    -  기준선 아래 = 나쁨
  배리어 아래일 때만 '필요 상승률'(= 기준선/종가 - 1)을 부가 표시한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from data_utils import Quote, sanity_flag
from store import ki_touch

# 상태 코드
LIKELY   = "likely"     # 조기상환 유력
WATCH    = "watch"      # 경계
HOPELESS = "hopeless"   # 조기상환 난망
KI_HIT   = "ki_hit"     # KI 터치
MATURED  = "matured"    # 평가일정 종료
NODATA   = "nodata"     # 데이터 수집 실패

STATUS_LABEL = {
    LIKELY:   ("조기상환 유력", "🟢"),
    WATCH:    ("경계 구간",     "🟡"),
    HOPELESS: ("조기상환 난망", "🔴"),
    KI_HIT:   ("KI 터치",       "⚫"),
    MATURED:  ("평가일정 종료", "⬜"),
    NODATA:   ("데이터 없음",   "⚠️"),
}


@dataclass
class Leg:
    ticker: str
    display: str
    strike: float
    quote: Quote
    barrier_px: float | None = None
    ki_px: float | None = None
    level_pct: float | None = None
    buf_barrier: float | None = None
    buf_ki: float | None = None
    need_up: float | None = None          # 배리어 미달 시 필요 상승률
    ki: dict = field(default_factory=dict)
    warn: str | None = None
    is_worst: bool = False


@dataclass
class ProductView:
    id: str
    name: str
    status: str
    legs: list[Leg]
    worst: Leg | None = None
    eval_no: int | None = None
    eval_date: date | None = None
    dday: int | None = None
    barrier: float | None = None
    coupon_cum: float | None = None
    payout: float | None = None
    principal: float | None = None
    coupon_annual: float | None = None
    is_final: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return STATUS_LABEL[self.status][0]

    @property
    def icon(self) -> str:
        return STATUS_LABEL[self.status][1]


def next_evaluation(product: dict, today: date):
    """오늘 포함, 아직 오지 않은 가장 가까운 평가차수."""
    sched = sorted(product["schedule"], key=lambda s: s["date"])
    for s in sched:
        if s["date"] >= today:                       # ← `>` 아님
            return s, (s is sched[-1])
    return None, True


def evaluate(product: dict, quotes: dict[str, Quote],
             history: list[dict], thresholds: dict,
             today: date) -> ProductView:
    up, is_final = next_evaluation(product, today)

    legs: list[Leg] = []
    warnings: list[str] = []

    for ticker, meta in product["underlyings"].items():
        q = quotes.get(ticker) or Quote(ticker, error="미수집")
        leg = Leg(ticker=ticker, display=meta["display"],
                  strike=float(meta["strike"]), quote=q)

        leg.ki_px = leg.strike * product["ki_barrier"]
        if up is not None:
            leg.barrier_px = leg.strike * up["barrier"]

        if q.ok:
            leg.level_pct = q.price / leg.strike
            leg.buf_ki = q.price / leg.ki_px - 1
            if leg.barrier_px:
                leg.buf_barrier = q.price / leg.barrier_px - 1
                if leg.buf_barrier < 0:
                    leg.need_up = leg.barrier_px / q.price - 1
            leg.warn = sanity_flag(leg.level_pct,
                                   thresholds["sanity_hi"], thresholds["sanity_lo"])
            if leg.warn:
                warnings.append(f"{leg.display}({ticker}): {leg.warn}")
            stale = q.stale_days(today)
            if stale is not None and stale >= 5:
                warnings.append(
                    f"{leg.display}({ticker}): 관측일이 {stale}일 전({q.obs_date}) — 상장폐지/티커 변경 확인")
        else:
            warnings.append(f"{leg.display}({ticker}): 수집 실패 — {q.error}")

        leg.ki = ki_touch(history, product["id"], ticker)
        legs.append(leg)

    view = ProductView(
        id=product["id"], name=product["name"], legs=legs,
        status=NODATA, is_final=is_final,
        principal=product.get("principal"),
        coupon_annual=product.get("coupon_annual"), warnings=warnings,
    )

    # worst-of = level_pct(종가/기준가)가 가장 낮은 기초자산
    valid = [l for l in legs if l.level_pct is not None]
    if valid:
        worst = min(valid, key=lambda l: l.level_pct)
        worst.is_worst = True
        view.worst = worst

    if up is not None:
        view.eval_no = up["no"]
        view.eval_date = up["date"]
        view.dday = (up["date"] - today).days
        view.barrier = up["barrier"]
        view.coupon_cum = up.get("coupon_cum")
        if view.coupon_cum is not None and view.principal:
            view.payout = view.principal * (1 + view.coupon_cum)

    # ── 상태 판정 ──
    if up is None:
        view.status = MATURED
    elif view.worst is None:
        view.status = NODATA
    elif any(l.ki.get("touched") for l in legs):
        view.status = KI_HIT
    else:
        b = view.worst.buf_barrier
        if b is None:
            view.status = NODATA
        elif b >= thresholds["likely"]:
            view.status = LIKELY
        elif b < thresholds["hopeless"]:
            view.status = HOPELESS
        else:
            view.status = WATCH

    # KI 근접 경보 (터치 전이라도)
    for l in legs:
        if l.buf_ki is not None and 0 <= l.buf_ki <= thresholds["ki_near"]:
            warnings.append(
                f"{l.display}: KI까지 {l.buf_ki*100:.1f}%p — 근접 경보")

    return view


def to_history_rows(view: ProductView, obs_fallback: date) -> list[dict]:
    rows = []
    for l in view.legs:
        if not l.quote.ok:
            continue
        rows.append({
            "date":        (l.quote.obs_date or obs_fallback).strftime("%Y-%m-%d"),
            "product":     view.id,
            "ticker":      l.ticker,
            "close":       round(l.quote.price, 6),
            "strike":      l.strike,
            "level_pct":   round(l.level_pct, 6) if l.level_pct is not None else "",
            "barrier_px":  round(l.barrier_px, 6) if l.barrier_px else "",
            "buf_barrier": round(l.buf_barrier, 6) if l.buf_barrier is not None else "",
            "ki_px":       round(l.ki_px, 6) if l.ki_px else "",
            "buf_ki":      round(l.buf_ki, 6) if l.buf_ki is not None else "",
        })
    return rows


def summarize(views: list[ProductView]) -> dict:
    counts = {k: 0 for k in STATUS_LABEL}
    for v in views:
        counts[v.status] += 1
    ddays = [v.dday for v in views if v.dday is not None]
    return {
        "counts": counts,
        "nearest_dday": min(ddays) if ddays else None,
        "warn_count": sum(len(v.warnings) for v in views),
    }


def preheader(views: list[ProductView], s: dict) -> str:
    """
    메일 제목은 그대로 두되, 받은편지함 미리보기에 신호를 실어 보낸다.
    Gmail/Outlook 목록에서 제목 옆에 회색으로 붙는 그 텍스트다.
    """
    c = s["counts"]
    parts = []
    if c[LIKELY]:   parts.append(f"상환유력 {c[LIKELY]}")
    if c[WATCH]:    parts.append(f"경계 {c[WATCH]}")
    if c[HOPELESS]: parts.append(f"난망 {c[HOPELESS]}")
    if c[KI_HIT]:   parts.append(f"KI터치 {c[KI_HIT]}")
    if c[NODATA]:   parts.append(f"수집실패 {c[NODATA]}")
    if s["nearest_dday"] is not None:
        parts.append(f"최근접 D-{s['nearest_dday']}")
    if s["warn_count"]:
        parts.append(f"점검 {s['warn_count']}")
    return " · ".join(parts) if parts else "이상 없음"
