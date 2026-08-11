"""
메일 본문 렌더러.

원칙
  - 마크다운 파이프 표를 버린다. Gmail에서 표로 안 보이고 텍스트 덩어리로 뭉갠다.
  - <style> 태그를 쓰지 않는다. Outlook이 통째로 날린다. 전부 인라인 style.
  - bgcolor를 항상 명시한다. 미지정 시 Gmail 다크모드가 색을 반전시켜
    초록/빨강이 뒤집혀 보인다.
  - 색에만 의존하지 않는다. 아이콘 + 한국어 라벨을 항상 같이 준다(색각·흑백 인쇄 대비).
  - 모바일 우선. 가로 8컬럼 표를 상품 카드로 쪼개 한 화면에 들어오게 한다.
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
}

STATUS_COLOR = {
    LIKELY: C["safe"], WATCH: C["watch"], HOPELESS: C["breach"],
    KI_HIT: "#3A2E4A", MATURED: C["muted"], NODATA: C["muted"],
}

FONT = ("-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo',"
        "'Malgun Gothic','맑은 고딕',Roboto,sans-serif")
MONO = "'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"

SCALE_MAX = 1.30   # 눈금자 오른쪽 끝 = 기준가의 130%


def _pct(v, nd=2, signed=False):
    if v is None:
        return "—"
    s = f"{v*100:+.{nd}f}%" if signed else f"{v*100:.{nd}f}%"
    return s


def _num(v, nd=2):
    return "—" if v is None else f"{v:,.{nd}f}"


def _ruler(level_pct, ki_ratio, barrier_ratio, color) -> str:
    """
    기준가 대비 위치 눈금자. div가 아니라 table로 만든다(Outlook 대응).
    ├ KI ────── 배리어 ────── 100% 까지의 눈금 위에서 현재 수준을 채운다.
    """
    if level_pct is None:
        return ""
    clamp = lambda x: max(0.0, min(100.0, x / SCALE_MAX * 100))
    cur = clamp(level_pct)
    marks = {round(clamp(ki_ratio), 3): "#3A2E4A"}
    if barrier_ratio:
        marks[round(clamp(barrier_ratio), 3)] = C["deep"]

    # 현재수준도 브레이크포인트에 넣어야 채움 구간이 정확히 끊긴다
    stops = sorted({0.0, 100.0, round(cur, 3), *marks.keys()})

    def seg(w, bg):
        return (f'<td width="{w:.2f}%" bgcolor="{bg}" style="width:{w:.2f}%;'
                f'height:11px;line-height:11px;font-size:0;">&nbsp;</td>')

    cells = []
    for i, p in enumerate(stops):
        if p in marks and p > 0:
            cells.append(f'<td width="3" bgcolor="{marks[p]}" style="width:3px;'
                         f'height:11px;line-height:11px;font-size:0;">&nbsp;</td>')
        if i + 1 < len(stops):
            w = stops[i + 1] - p
            if w > 0:
                cells.append(seg(w, color if stops[i + 1] <= cur + 1e-6 else C["track"]))

    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'border="0" style="width:100%;border-collapse:collapse;">'
            f'<tr>{"".join(cells)}</tr></table>')


def _leg_block(leg, view) -> str:
    color = STATUS_COLOR[view.status] if leg.is_worst else C["muted"]
    if leg.buf_barrier is not None:
        color = (C["safe"] if leg.buf_barrier >= 0.10 else
                 C["watch"] if leg.buf_barrier >= -0.10 else C["breach"])
    if leg.ki.get("touched"):
        color = "#3A2E4A"

    name = (f'{leg.display}<span style="color:{C["muted"]};font-weight:400;'
            f'font-family:{MONO};font-size:11px;"> {leg.ticker}</span>')
    tag = ('<span style="background-color:#1F3A5F;color:#FFFFFF;font-size:10px;'
           'padding:1px 5px;border-radius:2px;margin-left:6px;'
           'letter-spacing:.04em;">WORST</span>') if leg.is_worst else ""

    if not leg.quote.ok:
        return (f'<tr><td style="padding:10px 0;border-top:1px solid {C["rule"]};'
                f'color:{C["breach"]};font-size:13px;">'
                f'{leg.display} ({leg.ticker}) — 수집 실패: {leg.quote.error}</td></tr>')

    need = (f' <span style="color:{C["breach"]};">({_pct(leg.need_up, 2, True)} 필요)</span>'
            if leg.need_up else "")

    ki_txt = ("터치 " + (leg.ki["date"] or "") if leg.ki.get("touched")
              else ("미확인" if not leg.ki.get("observed")
                    else f'최저 {_pct(leg.ki["min_level"])}'))

    warn = (f'<div style="margin-top:6px;font-size:12px;color:{C["breach"]};">'
            f'⚠️ {leg.warn}</div>') if leg.warn else ""

    return f"""<tr><td style="padding:12px 0 10px;border-top:1px solid {C['rule']};">
  <div style="font-size:14px;color:{C['ink']};font-weight:700;">{name}{tag}</div>
  <div style="margin:6px 0 7px;font-family:{MONO};font-size:13px;color:{C['ink']};">
    <span style="color:{color};font-weight:700;font-size:16px;">{_pct(leg.buf_barrier,2,True)}</span>
    <span style="color:{C['muted']};font-size:12px;"> 배리어 여유</span>{need}
  </div>
  {_ruler(leg.level_pct, view_ki_ratio(view), view.barrier, color)}
  <div style="margin-top:6px;font-family:{MONO};font-size:11px;color:{C['muted']};">
    종가 {_num(leg.quote.price)} · 기준가 {_num(leg.strike)} · 수준 {_pct(leg.level_pct)}
    · KI여유 {_pct(leg.buf_ki,1,True)} · {ki_txt}
    · 관측 {leg.quote.obs_date}
  </div>{warn}
</td></tr>"""


def view_ki_ratio(view: ProductView) -> float:
    for l in view.legs:
        if l.ki_px and l.strike:
            return l.ki_px / l.strike
    return 0.35


def _product_card(view: ProductView) -> str:
    color = STATUS_COLOR[view.status]
    if view.eval_date:
        head = (f'{view.eval_no}차 평가 {view.eval_date:%Y-%m-%d} · D-{view.dday}'
                f' · Barrier {view.barrier*100:.0f}%'
                f'{" · 만기" if view.is_final else ""}')
    else:
        head = "평가일정 종료"

    payout = ""
    if view.payout:
        payout = (f'<div style="margin-top:8px;font-family:{MONO};font-size:12px;'
                  f'color:{C["muted"]};">조기상환 시 세전 수령액 '
                  f'<span style="color:{C["ink"]};font-weight:700;">'
                  f'{view.payout:,.0f}원</span> '
                  f'(원금 {view.principal:,.0f} × 누적 {view.coupon_cum*100:.2f}%)</div>')

    verdict = ""
    if view.worst and view.worst.need_up:
        verdict = (f'<div style="margin-top:8px;font-size:12px;color:{C["breach"]};">'
                   f'{view.worst.display} 기준 {view.dday}일 내 '
                   f'{view.worst.need_up*100:.1f}% 상승 필요</div>')
    elif view.worst and view.worst.buf_barrier is not None and view.status == LIKELY:
        verdict = (f'<div style="margin-top:8px;font-size:12px;color:{C["safe"]};">'
                   f'{view.worst.display} 기준 배리어까지 '
                   f'{abs(view.worst.buf_barrier)*100:.1f}%p 여유</div>')

    legs = "".join(_leg_block(l, view) for l in
                   sorted(view.legs, key=lambda x: (x.level_pct is None, x.level_pct or 0)))

    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       bgcolor="{C['paper']}" style="width:100%;border-collapse:collapse;
       background-color:{C['paper']};border:1px solid {C['rule']};margin-bottom:16px;">
  <tr><td bgcolor="{color}" style="background-color:{color};height:4px;line-height:4px;font-size:0;">&nbsp;</td></tr>
  <tr><td style="padding:14px 16px 4px;">
    <div style="font-size:11px;color:{C['muted']};letter-spacing:.06em;">상품 {view.id}</div>
    <div style="font-size:16px;font-weight:800;color:{C['ink']};margin-top:2px;">{view.name}</div>
    <div style="font-family:{MONO};font-size:12px;color:{C['muted']};margin-top:4px;">{head}</div>
    <div style="margin-top:10px;font-size:14px;font-weight:800;color:{color};">
      {view.icon} {view.label}</div>
    {verdict}{payout}
  </td></tr>
  <tr><td style="padding:6px 16px 14px;">
    <div style="font-size:10px;color:{C['muted']};padding-bottom:2px;">
      눈금 <span style="color:#3A2E4A;font-weight:800;">┃</span>KI {view_ki_ratio(view)*100:.0f}%
      <span style="color:{C['deep']};font-weight:800;">┃</span>배리어 {view.barrier*100:.0f}%
      · 오른쪽 끝 = 기준가 {SCALE_MAX*100:.0f}%</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
           style="width:100%;border-collapse:collapse;">{legs}</table>
  </td></tr>
</table>""" if view.barrier else f"""
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


def render_html(views, summary, pre, comment, chart_cid, dashboard_url, today) -> str:
    cards = "".join(_product_card(v) for v in views)

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

    chart_block = ""
    if chart_cid:
        chart_block = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       bgcolor="{C['paper']}" style="width:100%;background-color:{C['paper']};
       border:1px solid {C['rule']};margin-bottom:16px;">
  <tr><td style="padding:14px 16px;">
    <div style="font-size:13px;font-weight:800;color:{C['ink']};">배리어 여유율 추이 (worst-of)</div>
    <div style="font-size:11px;color:{C['muted']};margin-top:3px;">
      0선 위 = 조기상환 구간</div>
    <img src="cid:{chart_cid}" width="600" alt="배리어 여유율 추이"
         style="display:block;width:100%;max-width:600px;height:auto;margin-top:10px;border:0;">
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
  <tr><td>{cards}{warn_block}{ai_block}{chart_block}{link}</td></tr>
  <tr><td style="padding:14px 2px 4px;border-top:1px solid {C['rule']};
      font-size:11px;color:{C['muted']};line-height:1.6;">
    여유율 = 종가 ÷ 기준선 − 1 (+ 기준선 위 / − 아래). worst-of = 기준가 대비 수준이 가장 낮은 기초자산.<br>
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
                     f"Barrier {v.barrier*100:.0f}%")
        L.append(f"  판정: {v.label}")
        for l in sorted(v.legs, key=lambda x: (x.level_pct is None, x.level_pct or 0)):
            if not l.quote.ok:
                L.append(f"   - {l.display}: 수집 실패 ({l.quote.error})")
                continue
            mark = " <worst" if l.is_worst else ""
            need = f" ({l.need_up*100:+.2f}% 필요)" if l.need_up else ""
            L.append(f"   - {l.display}{mark}: 배리어여유 {l.buf_barrier*100:+.2f}%{need}"
                     f" | 수준 {l.level_pct*100:.1f}% | KI여유 {l.buf_ki*100:+.1f}%"
                     f" | 관측 {l.quote.obs_date}")
        if v.payout:
            L.append(f"  조기상환 시 세전 {v.payout:,.0f}원")
        for w in v.warnings:
            L.append(f"  ! {w}")
        L.append("")
    if comment:
        L += ["[AI 코멘트]", comment, ""]
    return "\n".join(L)
