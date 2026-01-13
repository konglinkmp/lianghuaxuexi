from quant.strategy.strategy import check_buy_signal, calculate_stop_loss, calculate_take_profit
from quant.core.data_fetcher import get_stock_daily_history
import pandas as pd

def check_stocks(codes):
    results = []
    for code in codes:
        df = get_stock_daily_history(code)
        if df is not None and not df.empty:
            buy_signal = check_buy_signal(df)
            close = df.iloc[-1]['close']
            results.append({
                "code": code,
                "buy_signal": buy_signal,
                "close": close
            })
    return results

if __name__ == "__main__":
    codes = ["002131", "002195"]
    res = check_stocks(codes)
    print(res)
