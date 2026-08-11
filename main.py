import csv
from datetime import date
from config import (
    UNDERLYING_TICKERS,
    STRIKE_PRICES,
    EARLY_REDEMPTION_BARRIERS,
    EARLY_REDEMPTION_COUPONS,
    EVALUATION_DATES,
    KNOCK_IN_BARRIERS,
    EMAIL_CONFIG,
    TICKER_DISPLAY_NAMES,   # ← 추가
)
from data_utils import fetch_last_close
from email_utils import send_email

def job():
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')

    # 1) 데이터 수집 및 계산
    rows = []
    for ticker in UNDERLYING_TICKERS:
        strike      = STRIKE_PRICES[ticker]
        close_price = fetch_last_close(ticker)
        decline     = 1 - close_price / strike

        # 다음 평가차수
        upcoming = next((i for i, d in EVALUATION_DATES[ticker].items() if d > today), None)
        if not upcoming:
            continue

        # barrier 비율 (tuple인 경우 첫번째 요소 사용)
        raw_barrier = EARLY_REDEMPTION_BARRIERS[ticker][upcoming]
        barrier_ratio = raw_barrier[0] if isinstance(raw_barrier, tuple) else raw_barrier

        # 숫자·퍼센트 포맷팅
        close_s  = f"{close_price:.2f}"
        strike_s = f"{strike:.2f}"
        decline_s= "해당없음" if decline < 0 else f"{(decline*100):.2f}%"
        ki_s     = f"{(strike * KNOCK_IN_BARRIERS[ticker]):.2f}"
        barrier_s= f"{(barrier_ratio*100):.2f}%"
        eval_date= EVALUATION_DATES[ticker][upcoming].strftime('%Y-%m-%d')
        redemption_price = strike * barrier_ratio
        redemption_s = f"{redemption_price:.2f}"

        rows.append([
            TICKER_DISPLAY_NAMES.get(ticker, ticker),  # ← 변환된 이름 사용
            close_s, strike_s, decline_s,
            ki_s, str(upcoming), eval_date,
            barrier_s, redemption_s
        ])

    # 2) 마크다운 표 문자열 생성
    header = [
        "Ticker", "종가", "기준가격", "하락률",
        "Knock-in", "평가차수", "평가일",
        "Barrier", "상환가"
    ]
    sep = ["-" * len(h) for h in header]

    table_lines = []
    table_lines.append(" | ".join(header))
    table_lines.append(" | ".join(sep))
    for r in rows:
        table_lines.append(" | ".join(r))

    table_md = "\n".join(table_lines)

    # 3) 콘솔 출력
    print(table_md)

    # 4) CSV 파일 생성 (첨부용)
    output_file = 'els_report.csv'
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"\nCSV 파일 생성 완료: {output_file}")

    # 5) 이메일 전송
    send_email(
        subject=f"ELS Report ({today_str})",
        body=table_md,
        attachments=[("els_report.csv", output_file)],
        config=EMAIL_CONFIG
    )

if __name__ == "__main__":
    job()
