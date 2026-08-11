# 계정 설정 가이드

메일과 자동화를 붙이려면 이 순서대로 하면 된다. 10~15분 걸린다.

---

## 0. 🚨 먼저 — 노출된 앱 비밀번호 폐기

기존 `config.py`에 앱 비밀번호가 평문으로 있었다.

```python
'PASSWORD': 'ufrq************',      # ← 노출됨
```

**GitHub에 올라간 이상 이미 유출됐다고 가정해야 한다.** 공개 저장소는 봇이 상시 스캔하고,
비공개 저장소라도 협업자·포크·로그를 통해 새어나간다. 그리고 파일에서 지우고 커밋해도
**git 히스토리에는 영구히 남는다** — `git log -p`로 누구나 과거 버전을 볼 수 있다.

따라서 삭제가 아니라 **폐기 + 재발급**이 유일한 해결책이다.

1. https://myaccount.google.com/apppasswords 접속
2. 목록에서 해당 앱 비밀번호 찾아 **삭제(휴지통 아이콘)**
3. 같은 화면에서 새로 발급 (아래 1단계)

> 참고: 이 앱 비밀번호로 할 수 있는 건 해당 Gmail 계정으로 **메일을 보내는 것**이다.
> 계정 로그인이나 다른 구글 서비스 접근은 안 된다. 그래도 스팸 발송에 악용될 수 있으니
> 폐기는 반드시 해야 한다.

---

## 1. Gmail 앱 비밀번호 발급

Gmail SMTP는 계정 비밀번호를 받지 않는다. 16자리 앱 비밀번호가 따로 필요하다.

1. **2단계 인증을 먼저 켠다** — https://myaccount.google.com/signinoptions/twosv
   (이게 꺼져 있으면 앱 비밀번호 메뉴 자체가 안 보인다)
2. https://myaccount.google.com/apppasswords
3. 앱 이름에 `ELS Report` 입력 → 만들기
4. 나오는 **16자리**를 복사 (공백은 무시해도 된다)

이 창을 닫으면 다시 볼 수 없다. 바로 다음 단계로 넘어갈 것.

---

## 2-A. 로컬에서 돌릴 때

```bash
cp .env.example .env
```

`.env`를 열어 `ELS_SMTP_PASSWORD=` 뒤에 1단계에서 받은 16자리를 붙인다.

```bash
ELS_SMTP_PASSWORD=abcdefghijklmnop
```

`.env`는 `.gitignore`에 있어 커밋되지 않는다. `config.py`가 자동으로 읽는다.

```bash
python main.py --dry-run     # 메일 없이 preview.html만
python main.py               # 실제 발송
```

---

## 2-B. GitHub Actions로 매일 자동 실행할 때

저장소 → **Settings ▸ Secrets and variables ▸ Actions**

### Secrets 탭 → New repository secret

| Name | Value |
|---|---|
| `ELS_SMTP_HOST` | `smtp.gmail.com` |
| `ELS_SMTP_PORT` | `587` |
| `ELS_SMTP_USER` | `hyunseo.kang238@gmail.com` |
| `ELS_SMTP_PASSWORD` | 1단계에서 받은 16자리 |
| `ELS_MAIL_FROM` | `hyunseo.kang238@gmail.com` |
| `ELS_MAIL_TO` | `fan155@naver.com,leejy_93@naver.com` |
| `ANTHROPIC_API_KEY` | (선택) AI 코멘트용 |

### Variables 탭 → New repository variable

| Name | Value |
|---|---|
| `ELS_DASHBOARD_URL` | `https://<깃허브아이디>.github.io/<저장소이름>/` |

> Secrets는 한 번 저장하면 다시 볼 수 없고 로그에도 `***`로 마스킹된다.
> 대시보드 URL은 비밀이 아니므로 Variables에 둔다.

---

## 3. GitHub Pages 켜기

저장소 → **Settings ▸ Pages**

- Source: **Deploy from a branch**
- Branch: `main` / 폴더 `/docs` → Save

1~2분 뒤 `https://<아이디>.github.io/<저장소>/` 가 열린다.
아직 데이터가 없으면 "아직 생성된 데이터가 없다" 화면이 나온다 — 정상이다.

### 저장소가 Private이면

Pages는 유료(Pro 이상)다. 두 가지 선택지가 있다.

- 저장소를 Public으로 전환 → 단, **`.env`나 과거 커밋에 비밀번호가 없는지 먼저 확인**
- 대시보드를 포기하고 메일의 인라인 차트만 사용 → `ELS_DASHBOARD_URL`을 비워두면 링크가 안 나온다

---

## 4. 첫 실행

```bash
pip install -r requirements.txt

python backfill.py           # 발행일까지 소급. 1회만.
python main.py               # 리포트 + 메일
```

백필 출력에서 **급변동 스캔** 결과를 꼭 확인할 것. MU가 기준가의 249%인 이유가
액면분할인지 진짜 상승인지 여기서 갈린다.

Actions 쪽은 저장소 → **Actions ▸ ELS daily report ▸ Run workflow** 로 수동 실행해
한 번 검증한 뒤 스케줄에 맡기면 된다.

---

## 5. 수신 확인

### 네이버 메일로 받을 때

`fan155@naver.com`, `leejy_93@naver.com` 두 곳으로 간다.
Gmail에서 온 자동 메일은 **스팸함으로 분류되는 경우가 잦다.**

- 첫 메일이 안 오면 스팸함부터 확인
- 발신자를 **수신 허용 목록**에 추가 (네이버 메일 ▸ 환경설정 ▸ 스팸설정 ▸ 수신허용)
- 네이버는 외부 이미지를 기본 차단한다 → 차트가 안 보이면 상단 "이미지 보기"를 누르거나,
  발신자를 주소록에 추가하면 이후 자동 표시된다.
  (막대 눈금자는 CSS 배경색이라 이미지 차단과 무관하게 항상 보인다)

### 발송이 안 될 때

| 증상 | 원인 |
|---|---|
| `535 Authentication failed` | 계정 비밀번호를 넣었다. 앱 비밀번호 16자리여야 한다 |
| `설정 누락으로 전송 생략` | `ELS_SMTP_PASSWORD`가 비어 있다 |
| 아무 로그 없이 조용 | Actions 실행 자체가 안 된 것. Actions 탭에서 로그 확인 |

---

## 6. 아직 남은 확인 사항

| 항목 | 내용 |
|---|---|
| **쿠폰 충돌** ❗ | 상품 A의 연쿠폰이 기존 config에서 `0.088`(GSPC·KS200)과 `0.229`(N225·만기)로 엇갈렸다. 같은 worst-of 상품이므로 하나여야 한다. 일단 `0.088`로 두었으니 투자설명서로 확인할 것. **확정 전까지 '세전 수령액' 숫자는 신뢰하지 말 것** |
| **발행일** | `2026-06-18`(A), `2026-01-09`(B)는 평가 간격에서 역산한 값이다. 백필 시작점과 누적쿠폰 계산의 기준이므로 확인 필요 |
| **투자원금** | 양쪽 모두 1,000만원 자리표시자다 |
| **MU 기준가** | 종가가 기준가의 249.5%. 백필의 급변동 스캔 결과부터 볼 것 |
| **KI 관측 방식** | 전부 종가(`close`) 기준으로 설정했다. 장중 저가 기준 상품이면 `ki_observation`을 `intraday`로 |
