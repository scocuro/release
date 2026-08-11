"""
AI 한줄평.

설계 원칙
  1) 에이전트가 아니다. 고정 파이프라인 안의 '호출 1회'다.
     매일 같은 순서로 돌아야 어제 메일이 왜 저렇게 나왔는지 추적이 된다.
  2) 계산을 시키지 않는다. 여유율·D-day·worst-of는 전부 파이썬이 끝내고
     모델에는 결과만 넘긴다. 숫자를 맡기면 틀린 값을 자신 있게 쓴다.
  3) 검색 없이 시황을 물으면 지어낸다. 그래서 web_search 도구를 붙이거나,
     아예 '주어진 수치만 해석'으로 못을 박거나 둘 중 하나만 한다.
  4) 실패해도 절대 위로 예외를 올리지 않는다. 표가 본체고 코멘트는 부가물이다.
     여기서 예외가 튀면 알림 시스템이 '침묵으로' 실패한다 — 최악의 형태.
"""

from __future__ import annotations

import json
import os
from datetime import date

SYSTEM = """당신은 ELS(주가연계증권) 조기상환 모니터링 리포트에 붙는 짧은 코멘트를 쓴다.

절대 규칙
- 주어진 수치를 다시 계산하지 마라. 여유율·D-day·worst-of는 이미 확정된 값이다. 그대로 인용만 하라.
- 검색으로 확인되지 않은 시장 사실을 쓰지 마라. 근거가 없으면 "확인된 시황 근거 없음"이라고 쓰고 끝내라.
  기억에 의존해 지수 레벨, 실적, 금리, 이벤트 날짜를 추정하는 것을 금한다.
- 투자 권유·매수매도 의견·가격 전망을 쓰지 마라. 상태 서술과 관찰만 한다.
- 상품마다 1~2문장. 전체 4문장 이내. 한국어. 개조식(~함/~임) 문어체.
- 수치를 반복 나열하지 마라. 표에 이미 있다. 표가 답하지 못하는 '그래서 무엇을 봐야 하는가'만 쓴다."""

USER_TMPL = """오늘: {today}

확정된 계산 결과(JSON):
{payload}

위 상태에 대해 코멘트를 작성하라.
{search_note}"""

SEARCH_NOTE_ON = (
    "web_search로 각 worst-of 기초자산의 최근 동향을 확인해도 된다. "
    "검색 결과로 뒷받침되는 내용만 쓰고, 확인 못 한 것은 쓰지 마라."
)
SEARCH_NOTE_OFF = (
    "검색 도구가 없다. 위에 주어진 수치만 해석하고, 외부 시장 사실은 일절 쓰지 마라."
)


def _payload(views) -> str:
    out = []
    for v in views:
        w = v.worst
        out.append({
            "상품": v.id,
            "기초자산": v.name,
            "판정": v.label,
            "평가차수": v.eval_no,
            "평가일": str(v.eval_date) if v.eval_date else None,
            "D_day": v.dday,
            "배리어": f"{v.barrier*100:.0f}%" if v.barrier else None,
            "worst_of": w.display if w else None,
            "worst_배리어여유": f"{w.buf_barrier*100:+.2f}%" if (w and w.buf_barrier is not None) else None,
            "worst_필요상승률": f"{w.need_up*100:+.2f}%" if (w and w.need_up) else None,
            "worst_KI여유": f"{w.buf_ki*100:+.2f}%" if (w and w.buf_ki is not None) else None,
            "KI터치": any(l.ki.get("touched") for l in v.legs),
            "점검항목": v.warnings,
        })
    return json.dumps(out, ensure_ascii=False, indent=2)


def make_comment(views, cfg: dict, today: date) -> str | None:
    if not cfg.get("enabled") or not cfg.get("api_key"):
        return None
    try:
        import anthropic
    except ImportError:
        return "(코멘트 생략: anthropic 패키지 미설치)"

    try:
        client = anthropic.Anthropic(api_key=cfg["api_key"], timeout=cfg.get("timeout", 60))
        kwargs = dict(
            model=cfg["model"],
            max_tokens=700,
            system=SYSTEM,
            messages=[{
                "role": "user",
                "content": USER_TMPL.format(
                    today=today,
                    payload=_payload(views),
                    search_note=SEARCH_NOTE_ON if cfg.get("web_search") else SEARCH_NOTE_OFF,
                ),
            }],
        )
        if cfg.get("web_search"):
            kwargs["tools"] = [{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 4,
            }]

        resp = client.messages.create(**kwargs)

        # 응답은 text / server_tool_use / web_search_tool_result 블록이 섞여 온다.
        # 순서를 가정하지 말고 type으로 필터링한다.
        text = "\n".join(
            b.text for b in resp.content
            if getattr(b, "type", None) == "text" and getattr(b, "text", "").strip()
        ).strip()
        return text or "(코멘트 비어 있음)"
    except Exception as e:                       # noqa: BLE001
        return f"(코멘트 생성 실패: {type(e).__name__}: {e})"


def log_comment(path: str, today: date, comment: str | None) -> None:
    """생성된 코멘트를 날짜별로 남긴다.
    나중에 '8월에 뭐라고 했었지' 대조가 되고, 헛소리 패턴도 잡힌다."""
    if not comment:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"date": str(today), "comment": comment},
                           ensure_ascii=False) + "\n")
