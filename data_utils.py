import yfinance as yf
from datetime import date, timedelta

def fetch_last_close(ticker: str) -> float:
    tk = yf.Ticker(ticker)
    # last_price는 실시간에 가까운 마지막 가격을 반환합니다.
    last_price = tk.fast_info['last_price']
    return float(last_price)


def fetch_price_on_date(ticker: str, eval_date: date) -> float:
    """
    지정된 날짜(eval_date)의 종가를 반환합니다.
    yfinance의 end는 exclusive이므로 하루 더해 end로 전달합니다.
    """
    start = eval_date.isoformat()
    end = (eval_date + timedelta(days=1)).isoformat()
    df = yf.Ticker(ticker).history(start=start, end=end)
    if df.empty:
        raise ValueError(f"No data for {ticker} on {eval_date}")
    return float(df['Close'].iloc[0])
