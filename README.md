# ELS 조기상환 모니터

매일 아침 메일 1통 + GitHub Pages 대시보드로 ELS 조기상환 상태를 추적한다.

## 이 리포트가 답하는 질문

기존 표는 `하락률 33.81%` / `상환가 1255.64`를 보여줄 뿐, **"그래서 상환되나?"** 는 매일
직접 암산해야 했다. 이제 그 결론이 셀 안에 직접 박힌다.

> KOSPI200 기준 38일 내 **+28.4% 상승 필요** → 1차 조기상환 난망

---

> **계정·메일 설정은 [SETUP.md](SETUP.md)에 단계별로 정리했다.**

## ⚠️ 시작 전에 — 비밀정보

`config.py`에 메일 비밀번호나 API 키를 **절대 넣지 마라.** push하면 몇 분 안에 봇이 긁어간다.
전부 환경변수로 읽게 되어 있다.

- GitHub Actions → Settings ▸ Secrets and variables ▸ Actions
- 로컬 → `.env` (이미 `.gitignore`에 있다)

**이미 예전 `config.py`에 비밀번호를 넣고 push한 적이 있다면, 히스토리에 영구히 남는다.
지금 바로 앱 비밀번호와 API 키를 재발급할 것.**

| 이름 | 용도 |
|---|---|
| `ELS_SMTP_HOST` / `ELS_SMTP_PORT` | 기본 `smtp.gmail.com` / `465` |
| `ELS_SMTP_USER` / `ELS_SMTP_PASSWORD` | 계정 / **앱 비밀번호** (계정 비번 아님) |
| `ELS_MAIL_FROM` / `ELS_MAIL_TO` | 보내는 주소 / 받는 주소(쉼표 구분) |
| `ANTHROPIC_API_KEY` | AI 코멘트. 없으면 코멘트만 생략되고 리포트는 정상 발송 |
| `ELS_DASHBOARD_URL` | 메일 하단 대시보드 버튼 링크 (Actions variables) |

로컬은 `cp .env.example .env` 후 값만 채우면 `config.py`가 자동으로 읽는다.

---

## 설치와 첫 실행

```bash
pip install -r requirements.txt

# 1) config.py의 PRODUCTS를 실제 투자설명서 값으로 맞춘다
#    특히 issue_date / schedule / coupon_cum 은 자리표시자다 (# TODO 표시)

# 2) 발행일까지 소급 백필 — 딱 1회
python backfill.py

# 3) 메일 없이 결과만 확인
python main.py --dry-run     # preview.html 생성

# 4) 실전
python main.py
```

SMTP 설정 없이 결과물만 보고 싶으면:

```bash
python demo_preview.py
python -m http.server -d _demo 8000     # http://localhost:8000
```

---

## 백필을 왜 먼저 하나

`history.csv`가 없으면 세 가지가 동시에 안 된다.

1. **KI 터치 판정** — 당일 종가만으로는 과거에 KI를 찍었는지 알 수 없다.
   한 번 터치되면 상품 성격이 바뀌는데 그 상태 변수를 아무도 안 들고 있었다.
2. **추이 차트** — 관측치가 1개면 선이 안 그려진다.
3. **기준가 정합성 판별** — 종가가 기준가의 249%인 게 액면분할 때문인지 진짜 상승인지,
   시계열을 봐야 구분된다. 하루에 튀었으면 분할, 완만히 올랐으면 상승이다.
   `backfill.py`가 급변동일을 자동으로 찍어준다.

---

## 파일 구성

| 파일 | 역할 |
|---|---|
| `config.py` | 상품 단위 설정. ticker 단위 dict 5개를 상품 리스트로 바꿨다 |
| `data_utils.py` | 시세 수집. `Quote(price, obs_date, error)` — 관측일을 같이 돌려준다 |
| `compute.py` | worst-of 판정, 여유율 계산, 상태 분류 |
| `store.py` | `history.csv` append-only 저장소. KI 터치 이력의 단일 소스 |
| `render.py` | HTML 메일. 인라인 스타일, 표 기반 눈금자, 다크모드 안전 |
| `chart_utils.py` | matplotlib 차트. 한글 폰트 자동 탐색 + 영문 폴백 |
| `ai_comment.py` | 모델 호출 1회. 계산은 안 시키고 해석만 시킨다 |
| `email_utils.py` | 멀티파트 + CID 인라인 이미지 |
| `main.py` | 파이프라인 |
| `backfill.py` | 소급 백필 (1회) |
| `docs/index.html` | GitHub Pages 대시보드 |

---

## 원본 코드에서 고친 버그

| 위치 | 문제 |
|---|---|
| `d > today` | **평가일 당일에 그 차수를 건너뛰고 다음 차수를 표시**했다 → `>=` |
| `if not upcoming` | 차수가 0이면 falsy로 걸린다 → `is None` |
| `next((i for i, d in ...))` | dict 삽입 순서에 의존 → 날짜 정렬 후 선택 |
| `continue` | 만기 경과 종목이 **표에서 조용히 사라졌다** → `평가일정 종료` 상태로 표시 |
| `decline < 0 → "해당없음"` | MU가 **+149%** 라는 정보가 통째로 날아가고 CSV 숫자 컬럼도 오염 |
| `EARLY_REDEMPTION_COUPONS` | import만 하고 안 썼다 → 세전 수령액 표시 |
| `encoding='utf-8'` | 엑셀에서 한글이 깨진다 → `utf-8-sig` |
| 예외 처리 없음 | 한 종목 실패 시 **메일이 아예 안 온다**. 알림 시스템의 침묵 실패 → 종목별 격리 |

---

## 부호 규약 (전 파일 공통)

```
여유율 = 종가 ÷ 기준선 − 1
   +  기준선 위 = 좋음
   −  기준선 아래 = 나쁨
```

배리어 아래일 때만 **필요 상승률**(= 기준선 ÷ 종가 − 1)을 부가 표시한다.
하나의 규약만 쓰므로 메일·차트·대시보드 숫자가 항상 일치한다.

---

## 자동화

`.github/workflows/els-daily.yml` — 매 평일 07:00 KST 실행.

- **`fonts-nanum` 설치 단계를 지우지 마라.** 우분투 러너에는 한글 폰트가 없어서
  차트 축과 범례가 전부 두부(□□□)로 나온다.
- 실행 후 `data/`, `docs/data/`를 커밋한다 → Pages가 자동 재배포된다.
- Pages 설정: Settings ▸ Pages ▸ Source `main` / `/docs`

---

## AI 코멘트가 에이전트가 아닌 이유

이 워크플로는 순서가 완전히 고정돼 있다 — 수집 → 계산 → 판정 → 코멘트 → 발송.
모델이 "다음에 뭘 할까"를 고민할 지점이 없다.

에이전트로 만들면 매일 다르게 행동하고, 실패 지점이 늘고,
**어제 메일이 왜 저렇게 나왔는지 추적이 안 된다.** 금융 리포트에서는 치명적이다.

그래서 파이프라인 안의 **호출 1회**로만 쓴다. 원칙은 세 가지다.

1. 여유율·D-day·worst-of는 파이썬이 전부 계산해서 넘긴다. **숫자를 모델에 맡기지 않는다.**
2. 검색 없이 시황을 물으면 지어낸다. `web_search`를 붙이거나, 주어진 수치만 해석하게 못을 박거나 — 둘 중 하나만 한다.
3. 실패해도 예외를 위로 올리지 않는다. **표가 본체, 코멘트는 부가물.**

생성된 코멘트는 `data/comments.jsonl`에 날짜별로 쌓인다.
나중에 "8월에 뭐라고 했었지" 대조가 되고, 헛소리 패턴도 잡힌다.

---

## 아직 남은 것

- **상품 A 연쿠폰이 `0.088` vs `0.229`로 충돌한다** — 기존 config에서 ^GSPC/^KS200은 8.8%, ^N225와 만기쿠폰은 22.9%였다. 같은 worst-of 상품이니 하나여야 한다. 일단 8.8%로 두었고 기동 시 경고가 뜬다
- `issue_date`(A 2026-06-18 / B 2026-01-09)는 평가 간격에서 역산한 값이다. 확인 필요
- `principal` 1,000만원은 자리표시자다
- **MU 기준가 249.5%** — 발행사 공시 기준가 대조가 필요하다. 백필의 급변동 스캔 결과부터 볼 것
- KI 관측 방식(`ki_observation`)이 전부 `close`로 되어 있다. 장중 저가 기준 상품이면 수정 필요
- 상태 변화 시 즉시 별도 메일 — `detect_changes()`가 이벤트를 감지만 하고 있다. 발송 연결은 미구현
