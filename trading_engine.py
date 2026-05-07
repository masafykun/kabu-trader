import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from config import settings, WATCHLIST
from database import AISignal, NewsArticle
from market_data import MarketDataFetcher
from portfolio import PortfolioManager

logger = logging.getLogger(__name__)

ACTION_JP = {"buy": "買い", "sell": "売り", "hold": "保有", "wait": "様子見"}


class TradingEngine:
    def __init__(self):
        self.market  = MarketDataFetcher()
        self.portfolio = PortfolioManager()

    def _sentiment_score(self, db: Session, symbol: str, hours: int = 24) -> float:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        articles = (
            db.query(NewsArticle)
            .filter(
                NewsArticle.related_symbols.contains(f'"{symbol}"'),
                NewsArticle.sentiment_score != None,  # noqa: E711
                NewsArticle.created_at >= cutoff,
            )
            .all()
        )

        if not articles:
            return 50.0

        weighted_score = 0.0
        total_weight   = 0.0
        for a in articles:
            imp  = a.importance_score or 50.0
            sent = float(a.sentiment_score or 0.0)
            # sentiment (-1~1) → score (0~100)
            weighted_score += ((sent + 1.0) * 50.0) * imp
            total_weight   += imp

        return weighted_score / total_weight if total_weight > 0 else 50.0

    def generate_signal(self, db: Session, symbol: str) -> Optional[dict]:
        sentiment_score = self._sentiment_score(db, symbol)
        mkt             = self.market.calculate_signals(symbol)

        if mkt["price"] is None:
            logger.warning(f"株価取得失敗: {symbol}")
            return None

        price_trend = mkt["price_trend_score"]
        volume      = mkt["volume_score"]

        final_score = (
            sentiment_score * 0.40
            + price_trend   * 0.35
            + volume        * 0.25
        )

        if final_score >= settings.BUY_THRESHOLD:
            action = "buy"
        elif final_score <= settings.SELL_THRESHOLD:
            action = "sell"
        elif final_score < 50:
            action = "wait"
        else:
            action = "hold"

        reasons: list[str] = []
        if sentiment_score >= 60:
            reasons.append("ニュース感情がポジティブ")
        elif sentiment_score <= 40:
            reasons.append("ニュース感情がネガティブ")
        if price_trend >= 60:
            reasons.append("価格が上昇トレンド(MA5>MA20)")
        elif price_trend <= 40:
            reasons.append("価格が下降トレンド(MA5<MA20)")
        if volume >= 65:
            reasons.append("出来高増加")
        reason = "、".join(reasons) if reasons else "指標が中立的"

        sig = AISignal(
            symbol=symbol, action=action, score=final_score,
            reason=reason, news_sentiment=sentiment_score,
            price_trend=price_trend, volume_change=volume,
            current_price=mkt["price"], created_at=datetime.utcnow(),
        )
        db.add(sig)
        db.commit()

        logger.info(
            f"SIGNAL {symbol}: {ACTION_JP[action]} スコア={final_score:.1f} "
            f"(感情={sentiment_score:.1f} 価格={price_trend:.1f} 出来高={volume:.1f})"
        )
        return {
            "symbol":        symbol,
            "action":        action,
            "score":         final_score,
            "reason":        reason,
            "news_sentiment":sentiment_score,
            "price_trend":   price_trend,
            "volume_change": volume,
            "current_price": mkt["price"],
        }

    def generate_all_signals(self, db: Session) -> list[dict]:
        signals: list[dict] = []
        for symbol in WATCHLIST:
            try:
                sig = self.generate_signal(db, symbol)
                if sig:
                    signals.append(sig)
            except Exception as e:
                logger.error(f"Signal error ({symbol}): {e}")
        return signals

    def execute_signals(self, db: Session, signals: list[dict]) -> int:
        executed = 0
        for sig in signals:
            symbol = sig["symbol"]
            price  = sig["current_price"]
            if price is None:
                continue
            try:
                if sig["action"] == "buy":
                    t = self.portfolio.buy(db, symbol, price, sig["reason"], sig["score"])
                elif sig["action"] == "sell":
                    t = self.portfolio.sell(db, symbol, price, sig["reason"], sig["score"])
                else:
                    continue
                if t:
                    executed += 1
            except Exception as e:
                logger.error(f"Trade exec error ({symbol}): {e}")
        return executed
