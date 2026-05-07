import logging
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class MarketDataFetcher:
    def get_current_price(self, symbol: str) -> Optional[float]:
        try:
            hist = yf.Ticker(symbol).history(period="2d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception as e:
            logger.error(f"Price fetch error ({symbol}): {e}")
        return None

    def get_history(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        try:
            hist = yf.Ticker(symbol).history(period=f"{days}d")
            if not hist.empty:
                return hist
        except Exception as e:
            logger.error(f"History fetch error ({symbol}): {e}")
        return None

    def calculate_signals(self, symbol: str) -> dict:
        hist = self.get_history(symbol, days=30)

        neutral = {
            "price": None,
            "price_trend_score": 50.0,
            "volume_score": 50.0,
            "ma5": None,
            "ma20": None,
            "price_change_pct": 0.0,
        }

        if hist is None or len(hist) < 5:
            return neutral

        close  = hist["Close"]
        volume = hist["Volume"]

        current_price = float(close.iloc[-1])
        ma5  = float(close.tail(5).mean())
        ma20 = float(close.mean())

        # MA5 vs MA20 で上昇/下降トレンドを判定 (±10% を 0-100 にマッピング)
        if ma20 > 0:
            trend = (ma5 / ma20 - 1.0) * 100
            price_trend_score = max(0.0, min(100.0, (trend + 10) * 5))
        else:
            price_trend_score = 50.0

        # 直近5日平均出来高 vs 20日平均 (出来高増加 = 関心高まり)
        avg_vol_5  = float(volume.tail(5).mean())
        avg_vol_20 = float(volume.mean())
        if avg_vol_20 > 0:
            vol_change = (avg_vol_5 / avg_vol_20 - 1.0) * 100
            volume_score = max(0.0, min(100.0, 50 + vol_change * 2))
        else:
            volume_score = 50.0

        # 前日比
        price_1d_ago = float(close.iloc[-2]) if len(close) >= 2 else current_price
        price_change_pct = (current_price / price_1d_ago - 1.0) * 100 if price_1d_ago > 0 else 0.0

        return {
            "price": current_price,
            "price_trend_score": price_trend_score,
            "volume_score": volume_score,
            "ma5": ma5,
            "ma20": ma20,
            "price_change_pct": price_change_pct,
        }

    def get_prices_batch(self, symbols: list[str]) -> dict[str, Optional[float]]:
        result: dict[str, Optional[float]] = {}
        for symbol in symbols:
            result[symbol] = self.get_current_price(symbol)
        return result
