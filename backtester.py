"""Single stock moving average crossover backtester.

Long when the fast SMA is above the slow SMA, otherwise in cash.
The signal is lagged one day (decide on today's close, trade tomorrow),
which avoids look ahead bias. Transaction costs are charged on every change
in position.

"""
import argparse

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def load_prices(ticker, start, end):
    import yfinance as yf

    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"No data returned for {ticker}")
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return close.dropna().rename(ticker)


def sma_signal(prices, fast=50, slow=200):
    """1.0 when fast SMA > slow SMA, else 0.0. Cash until the slow SMA exists."""
    if fast >= slow:
        raise ValueError("fast window must be shorter than slow window")
    fast_ma = prices.rolling(fast).mean()
    slow_ma = prices.rolling(slow).mean()
    signal = (fast_ma > slow_ma).astype(float)
    signal[slow_ma.isna()] = 0.0
    return signal


def run_backtest(prices, signal, cost=0.001):
    """Daily returns of the strategy and of buy and hold.

    position(t) = signal(t-1): today's trade uses yesterday's close signal.
    cost is the fraction of value lost per unit of position change
    (0.001 = 0.1% per trade).
    """
    position = signal.shift(1).fillna(0.0)
    asset_ret = prices.pct_change().fillna(0.0)
    trades = position.diff().abs()
    trades.iloc[0] = abs(position.iloc[0])
    strategy_ret = position * asset_ret - trades * cost
    return pd.DataFrame(
        {"position": position, "strategy": strategy_ret, "buy_hold": asset_ret}
    )


def metrics(returns):
    equity = (1 + returns).cumprod()
    years = len(returns) / TRADING_DAYS
    std = returns.std()
    return {
        "total_return": equity.iloc[-1] - 1,
        "cagr": equity.iloc[-1] ** (1 / years) - 1,
        "volatility": std * np.sqrt(TRADING_DAYS),
        "sharpe": returns.mean() / std * np.sqrt(TRADING_DAYS) if std > 0 else 0.0,
        "max_drawdown": (equity / equity.cummax() - 1).min(),
    }


def report(result):
    rows = {
        "Strategy": metrics(result["strategy"]),
        "Buy and hold": metrics(result["buy_hold"]),
    }
    table = pd.DataFrame(rows).T
    fmt = {
        "total_return": "{:.1%}",
        "cagr": "{:.1%}",
        "volatility": "{:.1%}",
        "sharpe": "{:.2f}",
        "max_drawdown": "{:.1%}",
    }
    for col, f in fmt.items():
        table[col] = table[col].map(f.format)
    n_trades = int(result["position"].diff().abs().sum())
    print(table.to_string())
    print(f"\nPosition changes: {n_trades}")
    print(f"Days invested: {result['position'].mean():.1%}")


def plot(result, ticker, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    equity = (1 + result[["strategy", "buy_hold"]]).cumprod()
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(equity.index, equity["strategy"], label="Strategy")
    ax.plot(equity.index, equity["buy_hold"], label="Buy and hold")
    ax.set_yscale("log")
    ax.set_title(f"{ticker}: growth of 1 (log scale)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("ticker")
    p.add_argument("--start", default="2010-01-01")
    p.add_argument("--end", default="2026-01-01")
    p.add_argument("--fast", type=int, default=50)
    p.add_argument("--slow", type=int, default=200)
    p.add_argument("--cost", type=float, default=0.001)
    p.add_argument("--plot", default="equity_curve.png")
    args = p.parse_args()

    prices = load_prices(args.ticker, args.start, args.end)
    signal = sma_signal(prices, args.fast, args.slow)
    result = run_backtest(prices, signal, args.cost)
    print(f"{args.ticker} {args.start} to {args.end}, SMA {args.fast}/{args.slow}, "
          f"cost {args.cost:.2%} per trade\n")
    report(result)
    plot(result, args.ticker, args.plot)
    print(f"\nSaved {args.plot}")


if __name__ == "__main__":
    main()
