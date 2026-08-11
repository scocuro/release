"""
메일 본문 렌더러.

원칙
  - 마크다운 파이프 표를 버린다. Gmail에서 표로 안 보이고 텍스트 덩어리로 뭉갠다.
  - <style> 태그를 쓰지 않는다. Outlook이 통째로 날린다. 전부 인라인 style.
  - bgcolor를 항상 명시한다. 미지정 시 Gmail 다크모드가 색을 반전시킨다.
  - 색에만 의존하지 않는다. 아이콘 + 한국어 라벨을 항상 같이 준다.

막대 규약 (사용자 정의)
  왼쪽 끝 = 주가 0, 오른쪽 끝 = 기준가.
  종가 >= 기준가  ->  초록 100% 막대 하나. 눈금 없음.
  종가 <  기준가  ->  0부터 종가까지 색으로 채우고,
                      조기상환 트리거와 KI 위치에 검정 눈금을 세운다.
                      트리거에 얼마나 가까운지가 한눈에 보인다.
"""

from __future__ import annotations

from datetime import date

from compute import (HOPELESS, KI_HIT, LIKELY, MATURED, NODATA, WATCH,
                     ProductView)

C = {
    "ink":    "#12171F",
    "paper":  "#FFFFFF",
    "soft":   "#F2F4F1",
    "rule":   "#DCE0DA",
    "deep":   "#1F3A5F",
    "safe":   "#0E7C6B",
    "watch":  "#B5820A",
    "breach": "#B23A2E",
    "muted":  "#6A7280",
    "track":  "#E7EAE4",
    "tick":   "#000000",
}

STATUS_COLOR = {
    LIKELY: C["safe"], WATCH: C["watch"], HOPELESS: C["breach"],
    KI_HIT: "#3A2E4A", MATURED: C["muted"], NODATA: C["muted"],
}

FONT = ("-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo',"
        "'Malgun Gothic','맑은 고딕',Roboto,sans-serif")
MONO = "'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"


def _pct(v, nd=2, signed=False):
    if v is None:
        return "—"
    return f"{v*100:+.{nd}f}%" if signed else f"{v*100:.{nd}f}%"


def _num(v, nd=2):
    return "—" if v is None else f"{v:,.{nd}f}"


# ── 막대 ────────────────────────────────────────────────────────
def _bar(level_pct, ki_ratio, trigger_ratio, color) -> str:
    """
    왼쪽 끝 = 0원, 오른쪽 끝 = 기준가.
    종가 >= 기준가 -> 눈금 없는 초록 100% 막대.
    종가 <  기준가 -> 0~종가를 채우고, KI와 트리거 위치에 검정 세로줄 + 라벨.

    두 가지를 조심한다.
    1) 눈금을 3px짜리 별도 <td>로 만들면 Gmail이 퍼센트 셀을 100%로 정규화하면서
       px 셀을 0으로 짓눌러 눈금이 사라진다. border-left로 그려야 남는다.
    2) 눈금이 채워진 구간 안에 들어가면 색에 파묻혀 어느 선인지 안 보인다.
       (팔란티어 98.7%는 트리거 75%를 '넘어선' 건데 '닿은' 것처럼 읽힌다)
       그래서 막대 바로 아래에 눈금 위치를 맞춘 라벨 행을 깐다.
    """
    if level_pct is None:
        return ""

    H = "16px"

    def seg(w, bg, tick=False):
        border = f"border-left:3px solid {C['tick']};" if tick else ""
        return (f'<td width="{w:.2f}%" bgcolor="{bg}" style="width:{w:.2f}%;'
                f'height:{H};line-height:{H};font-size:0;{border}">&nbsp;</td>')

    def lab(w, text):
        return (f'<td width="{w:.2f}%" style="width:{w:.2f}%;font-size:9.5px;'
                f'line-height:1.2;color:{C["tick"]};white-space:nowrap;'
                f'padding-top:3px;text-align:left;">{text}</td>')

    if level_pct >= 1.0:
        bar_row = seg(100, C["safe"])
        lab_row = lab(100, "")
    else:
        # round()가 올림되면 채움 기준값이 stop보다 작아져서
        # 채움이 '현재 종가'가 아니라 '직전 눈금'에서 멈춘다.
        # 반올림한 값 하나만 쓰고, 그걸로만 비교한다.
        cur = round(max(0.0, min(100.0, level_pct * 100)), 3)
        marks = {}
        kp = round(ki_ratio * 100, 3)
        if 0 < kp < 100:
            marks[kp] = f"KI {ki_ratio*100:.0f}%"
        if trigger_ratio:
            tp = round(trigger_ratio * 100, 3)
            if 0 < tp < 100:
                marks[tp] = f"트리거 {trigger_ratio*100:.0f}%"

        stops = sorted({0.0, 100.0, cur, *marks})
        bars, labs = [], []
        for a, b in zip(stops, stops[1:]):
            w = b - a
            if w <= 0:
                continue
            bars.append(seg(w, color if b <= cur else C["track"],
                            tick=(a in marks)))
            labs.append(lab(w, marks.get(a, "")))
        bar_row, lab_row = "".join(bars), "".join(labs)

    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'border="0" style="width:100%;border-collapse:separate;border-spacing:0;'
            f'table-layout:fixed;">'
            f'<tr>{bar_row}</tr><tr>{lab_row}</tr></table>')


def _bar_caption(level_pct, ki_ratio, trigger_ratio) -> str:
    """
    막대만으로는 '눈금을 넘어선 것'과 '눈금에 막힌 것'이 헷갈린다.
    한 문장으로 못 박는다.
    """
    if level_pct is None:
        return ""
    if level_pct >= 1.0:
        txt = "종가가 기준가 이상 — 트리거 통과"
    elif trigger_ratio and level_pct >= trigger_ratio:
        txt = f"트리거 통과 · 막대 왼쪽 끝 0원 / 오른쪽 끝 기준가"
    elif trigger_ratio:
        txt = f"트리거 미달 · 막대 왼쪽 끝 0원 / 오른쪽 끝 기준가"
    else:
        txt = "막대 왼쪽 끝 0원 / 오른쪽 끝 기준가"
    return (f'<div style="margin-top:4px;font-size:10.5px;color:{C["muted"]};">'
            f'{txt}</div>')


# ── 상세 항목 (한 줄에 하나) ─────────────────────────────────────
def _row(label, value, color=None, strong=False, sub=None):
    vcol = color or C["ink"]
    size = "15px" if strong else "13px"
    weight = "700" if strong else "500"
    subhtml = (f'<div style="font-family:{FONT};font-size:11px;color:{C["muted"]};'
               f'margin-top:1px;">{sub}</div>') if sub else ""
    return (f'<tr>'
            f'<td style="padding:5px 0;font-size:12px;color:{C["muted"]};'
            f'white-space:nowrap;">{label}</td>'
            f'<td align="right" style="padding:5px 0;font-family:{MONO};'
            f'font-size:{size};font-weight:{weight};color:{vcol};'
            f'white-space:nowrap;">{value}{subhtml}</td>'
            f'</tr>')


def _leg_block(leg, view) -> str:
    if not leg.quote.ok:
        return (f'<tr><td style="padding:14px 0;border-top:1px solid {C["rule"]};'
                f'color:{C["breach"]};font-size:13px;">'
                f'{leg.display} ({leg.ticker}) — 수집 실패: {leg.quote.error}</td></tr>')

    b = leg.buf_barrier
    color = (C["safe"] if (b is not None and b >= 0.10) else
             C["watch"] if (b is not None and b >= -0.10) else C["breach"])
    if leg.ki.get("touched"):
        color = "#3A2E4A"

    tag = ('<span style="background-color:#1F3A5F;color:#FFFFFF;font-size:10px;'
           'padding:1px 5px;border-radius:2px;margin-left:6px;'
           'letter-spacing:.04em;">WORST</span>') if leg.is_worst else ""

    ki_ratio = leg.ki_px / leg.strike if leg.strike else 0.0
    tr_ratio = leg.barrier_px / leg.strike if (leg.barrier_px and leg.strike) else None

    # 헤드라인
    if leg.need_up:
        head_val = f'{_pct(leg.need_up, 2, True)} 상승 필요'
        head_sub = f'현재 트리거보다 {abs(b)*100:.2f}% 아래'
    else:
        head_val = f'{_pct(b, 2, True)} 여유'
        head_sub = '트리거 위 — 상환 조건 충족 중'

    rows = [
        _row("종가", _num(leg.quote.price),
             sub=f"{leg.quote.obs_date} 관측"),
        _row("기준가", _num(leg.strike)),
        _row("기준가 대비 종가", _pct(leg.level_pct), color=color, strong=True),
        _row("조기상환 트리거", _num(leg.barrier_px),
             sub=f"기준가의 {tr_ratio*100:.0f}%" if tr_ratio else None),
        _row("트리거까지", head_val, color=color, strong=True, sub=head_sub),
        _row("KI 가격", _num(leg.ki_px), sub=f"기준가의 {ki_ratio*100:.0f}%"),
        _row("KI까지", _pct(leg.buf_ki, 2, True)),
        _row("KI 터치",
             ("터치 " + (leg.ki["date"] or "") if leg.ki.get("touched")
              else ("미확인" if not leg.ki.get("observed") else "미터치")),
             color=("#3A2E4A" if leg.ki.get("touched") else C["muted"])),
    ]

    warn = (f'<div style="margin-top:9px;padding:7px 9px;background-color:#FBF4E6;'
            f'font-size:11.5px;color:{C["breach"]};line-height:1.5;">'
            f'⚠️ {leg.warn}</div>') if leg.warn else ""

    return f"""<tr><td style="padding:15px 0 13px;border-top:1px solid {C['rule']};">
  <div style="font-size:15px;color:{C['ink']};font-weight:800;">
    {leg.display}<span style="color:{C['muted']};font-weight:400;font-family:{MONO};
      font-size:11px;"> {leg.ticker}</span>{tag}</div>
  <div style="margin-top:9px;">{_bar(leg.level_pct, ki_ratio, tr_ratio, color)}</div>
  {_bar_caption(leg.level_pct, ki_ratio, tr_ratio)}
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
         style="width:100%;border-collapse:collapse;margin-top:9px;">{''.join(rows)}</table>
  {warn}
</td></tr>"""


def _product_card(view: ProductView, chart_cid=None) -> str:
    color = STATUS_COLOR[view.status]

    if not view.barrier:
        return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       bgcolor="{C['paper']}" style="width:100%;border-collapse:collapse;
       background-color:{C['paper']};border:1px solid {C['rule']};margin-bottom:16px;">
  <tr><td bgcolor="{color}" style="background-color:{color};height:4px;line-height:4px;font-size:0;">&nbsp;</td></tr>
  <tr><td style="padding:14px 16px;">
    <div style="font-size:16px;font-weight:800;color:{C['ink']};">{view.name}</div>
    <div style="margin-top:8px;font-size:14px;font-weight:800;color:{color};">
      {view.icon} {view.label}</div>
  </td></tr>
</table>"""

    head = (f'{view.eval_no}차 평가 {view.eval_date:%Y-%m-%d} · D-{view.dday}'
            f' · 트리거 기준가의 {view.barrier*100:.0f}%'
            f'{" · 만기" if view.is_final else ""}')

    payout = ""
    if view.payout:
        payout = (f'<div style="margin-top:8px;font-family:{MONO};font-size:12px;'
                  f'color:{C["muted"]};">조기상환 시 세전 '
                  f'<span style="color:{C["ink"]};font-weight:700;">'
                  f'{view.payout:,.0f}원</span> '
                  f'(원금 {view.principal:,.0f} × 누적 {view.coupon_cum*100:.2f}%)</div>')

    verdict = ""
    if view.worst and view.worst.need_up:
        verdict = (f'<div style="margin-top:8px;font-size:13px;color:{C["breach"]};">'
                   f'{view.worst.display} 기준 {view.dday}일 내 '
                   f'{view.worst.need_up*100:.1f}% 상승 필요</div>')
    elif view.worst and view.worst.buf_barrier is not None and view.status == LIKELY:
        verdict = (f'<div style="margin-top:8px;font-size:13px;color:{C["safe"]};">'
                   f'{view.worst.display} 기준 트리거까지 '
                   f'{abs(view.worst.buf_barrier)*100:.1f}%p 여유</div>')

    legs = "".join(_leg_block(l, view) for l in
                   sorted(view.legs, key=lambda x: (x.level_pct is None, x.level_pct or 0)))

    chart = ""
    if chart_cid:
        chart = f"""<tr><td style="padding:4px 16px 16px;">
  <div style="border-top:1px solid {C['rule']};padding-top:13px;">
    <div style="font-size:12px;font-weight:700;color:{C['ink']};">기준가 대비 종가 추이</div>
    <div style="font-size:10.5px;color:{C['muted']};margin-top:2px;">
      점선 = 조기상환 트리거 / KI</div>
    <img src="cid:{chart_cid}" width="568" alt="기준가 대비 종가 추이"
         style="display:block;width:100%;max-width:568px;height:auto;margin-top:8px;border:0;">
  </div></td></tr>"""

    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       bgcolor="{C['paper']}" style="width:100%;border-collapse:collapse;
       background-color:{C['paper']};border:1px solid {C['rule']};margin-bottom:16px;">
  <tr><td bgcolor="{color}" style="background-color:{color};height:4px;line-height:4px;font-size:0;">&nbsp;</td></tr>
  <tr><td style="padding:14px 16px 4px;">
    <div style="font-size:11px;color:{C['muted']};letter-spacing:.06em;">상품 {view.id}</div>
    <div style="font-size:16px;font-weight:800;color:{C['ink']};margin-top:2px;">{view.name}</div>
    <div style="font-family:{MONO};font-size:12px;color:{C['muted']};margin-top:4px;">{head}</div>
    <div style="margin-top:11px;font-size:15px;font-weight:800;color:{color};">
      {view.icon} {view.label}</div>
    {verdict}{payout}
  </td></tr>
  <tr><td style="padding:2px 16px 10px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
           style="width:100%;border-collapse:collapse;">{legs}</table>
  </td></tr>
  {chart}
</table>"""


def render_html(views, summary, pre, comment, chart_cids, dashboard_url, today) -> str:
    chart_cids = chart_cids or {}
    cards = "".join(_product_card(v, chart_cids.get(v.id)) for v in views)

    warns = []
    for v in views:
        for w in v.warnings:
            warns.append(f'<li style="margin-bottom:5px;">[{v.id}] {w}</li>')
    warn_block = ""
    if warns:
        warn_block = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       bgcolor="#FDF6EC" style="width:100%;background-color:#FDF6EC;
       border-left:3px solid {C['watch']};margin-bottom:16px;">
  <tr><td style="padding:12px 14px;">
    <div style="font-size:13px;font-weight:800;color:{C['ink']};">점검 필요</div>
    <ul style="margin:8px 0 0;padding-left:18px;font-size:12px;color:{C['ink']};
        line-height:1.55;">{''.join(warns)}</ul>
  </td></tr></table>"""

    ai_block = ""
    if comment:
        ai_block = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       bgcolor="{C['soft']}" style="width:100%;background-color:{C['soft']};
       border:1px solid {C['rule']};margin-bottom:16px;">
  <tr><td style="padding:13px 15px;">
    <div style="font-size:11px;color:{C['muted']};letter-spacing:.06em;">AI 코멘트</div>
    <div style="margin-top:7px;font-size:13px;line-height:1.65;color:{C['ink']};
         white-space:pre-wrap;">{comment}</div>
    <div style="margin-top:9px;font-size:10px;color:{C['muted']};">
      참고용 요약이며 투자판단의 근거가 아님. 수치는 위 표가 원본.</div>
  </td></tr></table>"""

    link = ""
    if dashboard_url:
        link = f"""<div style="text-align:center;margin:4px 0 18px;">
  <a href="{dashboard_url}" style="display:inline-block;background-color:{C['deep']};
     color:#FFFFFF;text-decoration:none;font-size:13px;font-weight:700;
     padding:11px 22px;border-radius:3px;">대시보드에서 전체 추이 보기</a></div>"""

    return f"""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only">
<meta name="supported-color-schemes" content="light only">
</head>
<body style="margin:0;padding:0;background-color:{C['soft']};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{pre}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       bgcolor="{C['soft']}" style="width:100%;background-color:{C['soft']};">
<tr><td align="center" style="padding:18px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
       style="width:100%;max-width:600px;font-family:{FONT};">
  <tr><td style="padding:0 0 14px;">
    <div style="font-size:19px;font-weight:800;color:{C['ink']};">ELS 조기상환 모니터</div>
    <div style="font-family:{MONO};font-size:12px;color:{C['muted']};margin-top:3px;">
      {today:%Y-%m-%d} · {pre}</div>
  </td></tr>
  <tr><td>{cards}{warn_block}{ai_block}{link}</td></tr>
  <tr><td style="padding:14px 2px 4px;border-top:1px solid {C['rule']};
      font-size:11px;color:{C['muted']};line-height:1.6;">
    조기상환 트리거 = 해당 평가일에 이 가격 이상이어야 조기상환되는 기준가격.<br>
    worst-of = 기준가 대비 종가가 가장 낮은 기초자산. 상환 여부는 worst-of가 결정.<br>
    관측일은 각 시장의 마지막 거래일이며 실행일과 다를 수 있음. 자동 생성 리포트.
  </td></tr>
</table></td></tr></table></body></html>"""


def render_text(views, summary, pre, comment, today) -> str:
    """HTML 미지원 클라이언트용 대체본."""
    L = [f"ELS 조기상환 모니터  {today:%Y-%m-%d}", pre, ""]
    for v in views:
        L.append(f"[{v.id}] {v.name}")
        if v.eval_date:
            L.append(f"  {v.eval_no}차 {v.eval_date:%Y-%m-%d} (D-{v.dday}) "
                     f"트리거 기준가의 {v.barrier*100:.0f}%")
        L.append(f"  판정: {v.label}")
        for l in sorted(v.legs, key=lambda x: (x.level_pct is None, x.level_pct or 0)):
            if not l.quote.ok:
                L.append(f"   - {l.display}: 수집 실패 ({l.quote.error})")
                continue
            mark = " <worst" if l.is_worst else ""
            L.append(f"   - {l.display}{mark}")
            L.append(f"       종가 {l.quote.price:,.2f} ({l.quote.obs_date})")
            L.append(f"       기준가 {l.strike:,.2f} / 기준가 대비 {l.level_pct*100:.2f}%")
            L.append(f"       조기상환 트리거 {l.barrier_px:,.2f}")
            L.append(f"       트리거까지 " +
                     (f"{l.need_up*100:+.2f}% 상승 필요" if l.need_up
                      else f"{l.buf_barrier*100:+.2f}% 여유"))
            L.append(f"       KI 가격 {l.ki_px:,.2f} / KI까지 {l.buf_ki*100:+.2f}%"
                     f" / {'터치' if l.ki['touched'] else '미터치'}")
        if v.payout:
            L.append(f"  조기상환 시 세전 {v.payout:,.0f}원")
        for w in v.warnings:
            L.append(f"  ! {w}")
        L.append("")
    if comment:
        L += ["[AI 코멘트]", comment, ""]
    return "\n".join(L)
