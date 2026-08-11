import matplotlib.pyplot as plt
import io

def generate_price_chart(ticker: str) -> io.BytesIO:
    df = __import__('yfinance').Ticker(ticker).history(period='1y')
    plt.figure(figsize=(8, 4))
    plt.plot(df.index, df['Close'])
    plt.title(f"{ticker} 1Y 가격 추이")
    plt.xlabel('Date')
    plt.ylabel('Close Price')
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    return buf
