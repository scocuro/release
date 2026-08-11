"""
ELS 모니터링 설정.

┌────────────────────────────────────────────────────────────────┐
│ ⚠️  이 파일에는 비밀정보를 절대 넣지 않는다.                     │
│                                                                │
│ 기존 config.py에 Gmail 앱 비밀번호가 평문으로 있었다.            │
│ GitHub에 올라간 이상 히스토리에 영구히 남으므로, 파일에서        │
│ 지우는 것만으로는 해결되지 않는다. 반드시 재발급할 것.           │
│   https://myaccount.google.com/apppasswords                    │
└────────────────────────────────────────────────────────────────┘

기존 config 대비 달라진 점
  - ticker 단위 dict 9개  ->  '상품' 단위 리스트 1개
    ^N225/^GSPC/^KS200이 같은 값을 3번씩 반복하던 것이 1번으로 줄었다.
    worst-of 판정이 상품 안에서 자연스럽게 끝난다.
  - EARLY_REDEMPTION_* 와 MATURITY_* 를 하나의 schedule로 합쳤다.
    만기평가일도 '마지막 차수'일 뿐이라 따로 둘 이유가 없었다.
  - barrier가 tuple/float로 섞여 오던 것을 로딩 시점에 정규화한다.
"""

from __future__ import annotations

import os
from datetime import date

# .env 자동 로드 (있으면). python-dotenv가 없어도 동작하도록 직접 파싱한다.
_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_ENV):
    with open(_ENV, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))

# ──────────────────────────────────────────────────────────────
# 상품 정의
# ──────────────────────────────────────────────────────────────
# coupon_annual : 연율(세전). 차수별 누적수익률은 발행일로부터의 경과기간으로
#                 자동 계산된다.  누적 = 연율 × 경과일수/365
# ki_observation: 'close'    종가 기준 KI (대부분의 최근 발행분)
#                 'intraday' 장중 저가 기준 KI (구형 상품)

PRODUCTS = [
    {
        "id": "A",
        "name": "니케이225 / S&P500 / KOSPI200",
        "note": "제455회 ELS (지수형)",
        "issue_date": date(2026, 6, 18),   # TODO 역산값(3개월 스텝 3년물). 투자설명서로 확인
        "principal": 10_000_000,           # TODO 실제 투자원금
        "ki_barrier": 0.35,
        "ki_observation": "close",
        # 쿠폰 확인 완료 (2026-08, 사용자 확인): 지수형 연 22.9%
        "coupon_annual": 0.2290,
        "underlyings": {
            "^N225":  {"display": "니케이225", "strike": 72353.96},
            "^GSPC":  {"display": "S&P500",   "strike": 7472.79},
            "^KS200": {"display": "KOSPI200", "strike": 1477.22},
        },
        "schedule": [
            {"no":  1, "date": date(2026,  9, 18), "barrier": 0.85},
            {"no":  2, "date": date(2026, 12, 22), "barrier": 0.85},
            {"no":  3, "date": date(2027,  3, 19), "barrier": 0.85},
            {"no":  4, "date": date(2027,  6, 22), "barrier": 0.80},
            {"no":  5, "date": date(2027,  9, 22), "barrier": 0.80},
            {"no":  6, "date": date(2027, 12, 22), "barrier": 0.80},
            {"no":  7, "date": date(2028,  3, 22), "barrier": 0.75},
            {"no":  8, "date": date(2028,  6, 22), "barrier": 0.75},
            {"no":  9, "date": date(2028,  9, 21), "barrier": 0.70},
            {"no": 10, "date": date(2028, 12, 22), "barrier": 0.70},
            {"no": 11, "date": date(2029,  3, 22), "barrier": 0.70},
            {"no": 12, "date": date(2029,  6, 27), "barrier": 0.70},   # 만기평가일
        ],
    },
    {
        "id": "B",
        "name": "팔란티어 / 마이크론테크놀로지",
        "note": "종목형 (2-star)",
        "issue_date": date(2026, 1, 9),    # TODO 역산값(6개월 스텝 3년물). 투자설명서로 확인
        "principal": 10_000_000,           # TODO 실제 투자원금
        "ki_barrier": 0.25,                # 44.3725/177.49 = 86.2725/345.09 = 0.25
        "ki_observation": "close",
        "coupon_annual": 0.2200,
        "underlyings": {
            "PLTR": {"display": "팔란티어",          "strike": 177.49},
            "MU":   {"display": "마이크론테크놀로지", "strike": 345.09},
        },
        "schedule": [
            {"no": 1, "date": date(2026,  7,  9), "barrier": 0.80},
            {"no": 2, "date": date(2027,  1,  8), "barrier": 0.75},
            {"no": 3, "date": date(2027,  7,  9), "barrier": 0.75},
            {"no": 4, "date": date(2028,  1,  7), "barrier": 0.75},
            {"no": 5, "date": date(2028,  7,  7), "barrier": 0.60},
            {"no": 6, "date": date(2029,  1,  9), "barrier": 0.55},     # 만기평가일
        ],
    },
]

# ──────────────────────────────────────────────────────────────
# 판정 임계값
# ──────────────────────────────────────────────────────────────
THRESHOLDS = {
    # worst-of의 배리어 여유율 기준 (여유율 = 종가/배리어가격 - 1)
    "likely":   0.10,    # +10% 이상 -> 조기상환 유력
    "hopeless": -0.10,   # -10% 미만 -> 조기상환 난망
    "ki_near":  0.10,    # KI까지 여유 +10% 이내 -> KI 근접 경보
    # 데이터 정합성: 종가/기준가가 이 범위를 벗어나면 분할·병합 의심
    "sanity_hi": 2.50,   # MU는 액면분할 아닌 실제 상승으로 확인됨(2026-08 백필)
    "sanity_lo": 0.40,
    # 평가일 임박 알림
    "dday_alert": [5, 1],
}

# ──────────────────────────────────────────────────────────────
# 경로
# ──────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(BASE_DIR, "data", "history.csv")
STATE_PATH   = os.path.join(BASE_DIR, "data", "state.json")
DOCS_DIR     = os.path.join(BASE_DIR, "docs")
DOCS_DATA    = os.path.join(DOCS_DIR, "data")

# GitHub Pages 대시보드 주소 (메일 하단 링크). 비워두면 링크 미표시.
DASHBOARD_URL = os.environ.get("ELS_DASHBOARD_URL", "")

# ──────────────────────────────────────────────────────────────
# 메일
# ──────────────────────────────────────────────────────────────
# 주소는 비밀이 아니므로 기본값으로 둔다. 비밀번호만 환경변수 필수.
#   로컬:  export ELS_SMTP_PASSWORD='새로_발급한_앱비밀번호'
#   Actions: Settings > Secrets and variables > Actions > New repository secret
EMAIL_CONFIG = {
    "host":     os.environ.get("ELS_SMTP_HOST", "smtp.gmail.com"),
    "port":     int(os.environ.get("ELS_SMTP_PORT", "587")),   # 587=STARTTLS, 465=SSL
    "user":     os.environ.get("ELS_SMTP_USER", "hyunseo.kang238@gmail.com"),
    "password": os.environ.get("ELS_SMTP_PASSWORD", ""),       # ❗ 코드에 넣지 말 것
    "sender":   os.environ.get("ELS_MAIL_FROM", "hyunseo.kang238@gmail.com"),
    "to": [x.strip() for x in os.environ.get(
        "ELS_MAIL_TO", "fan155@naver.com,leejy_93@naver.com").split(",") if x.strip()],
}

# ──────────────────────────────────────────────────────────────
# AI 한줄평
# ──────────────────────────────────────────────────────────────
AI_CONFIG = {
    "enabled":    os.environ.get("ELS_AI_ENABLED", "1") == "1",
    "api_key":    os.environ.get("ANTHROPIC_API_KEY", ""),
    "model":      os.environ.get("ELS_AI_MODEL", "claude-sonnet-4-6"),
    "web_search": os.environ.get("ELS_AI_WEB_SEARCH", "1") == "1",
    "timeout":    60,
}


# ──────────────────────────────────────────────────────────────
def normalized_products():
    """
    - barrier를 float로 정규화 (레거시 tuple 대응)
    - coupon_annual + issue_date -> 차수별 coupon_cum 자동 계산
    - schedule을 날짜순 정렬 (dict 삽입순서 의존 제거)
    """
    out = []
    for p in PRODUCTS:
        q = dict(p)
        issue = p["issue_date"]
        annual = p.get("coupon_annual")
        sched = []
        for s in sorted(p["schedule"], key=lambda x: x["date"]):
            r = dict(s)
            b = r["barrier"]
            r["barrier"] = float(b[0]) if isinstance(b, (tuple, list)) else float(b)
            if "coupon_cum" not in r and annual is not None:
                r["coupon_cum"] = annual * (r["date"] - issue).days / 365.0
            sched.append(r)
        q["schedule"] = sched
        out.append(q)
    return out


def all_tickers():
    seen, out = set(), []
    for p in PRODUCTS:
        for t in p["underlyings"]:
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


def validate() -> list[str]:
    """기동 시 설정 문제를 소리내어 알린다. 조용히 틀린 리포트가 나가는 것보다 낫다."""
    msgs = []
    if not EMAIL_CONFIG["password"]:
        msgs.append("ELS_SMTP_PASSWORD 환경변수가 비어 있다 — 메일이 발송되지 않는다.")
    if not EMAIL_CONFIG["to"]:
        msgs.append("ELS_MAIL_TO 가 비어 있다.")
    if AI_CONFIG["enabled"] and not AI_CONFIG["api_key"]:
        msgs.append("ANTHROPIC_API_KEY 가 없다 — AI 코멘트만 생략되고 리포트는 정상 발송된다.")
    for p in PRODUCTS:
        if p.get("coupon_conflict"):
            msgs.append(f"[{p['id']}] {p['coupon_conflict']}")
        last = max(s["date"] for s in p["schedule"])
        span = (last - p["issue_date"]).days / 365.25
        if not (0.4 <= span <= 6):
            msgs.append(f"[{p['id']}] 발행일~만기 {span:.1f}년 — issue_date 확인 요망")
        for t, m in p["underlyings"].items():
            if not m.get("strike"):
                msgs.append(f"[{p['id']}] {t} 기준가 누락")
    return msgs
