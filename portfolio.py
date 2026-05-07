import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from database import CashBalance, Position, Trade

logger = logging.getLogger(__name__)


class PortfolioManager:
    def _ensure_cash(self, db: Session) -> CashBalance:
        balance = db.query(CashBalance).first()
        if not balance:
            balance = CashBalance(amount=settings.INITIAL_CAPITAL, updated_at=datetime.utcnow())
            db.add(balance)
            db.commit()
            db.refresh(balance)
        return balance

    def get_cash(self, db: Session) -> float:
        return self._ensure_cash(db).amount

    def get_position(self, db: Session, symbol: str) -> Optional[Position]:
        return db.query(Position).filter(Position.symbol == symbol).first()

    def get_all_positions(self, db: Session) -> list[Position]:
        return db.query(Position).filter(Position.shares > 0).all()

    def buy(
        self,
        db: Session,
        symbol: str,
        price: float,
        reason: str = "",
        score: float = 0.0,
    ) -> Optional[Trade]:
        balance = self._ensure_cash(db)
        invest = balance.amount * settings.MAX_POSITION_PCT

        if invest < price:
            logger.warning(f"BUY skip {symbol}: 投資可能額 {invest:.0f} < 株価 {price:.0f}")
            return None

        shares = invest / price
        total  = shares * price

        balance.amount    -= total
        balance.updated_at = datetime.utcnow()

        position = self.get_position(db, symbol)
        if position:
            total_shares = position.shares + shares
            total_cost   = position.shares * position.avg_cost + total
            position.avg_cost   = total_cost / total_shares
            position.shares     = total_shares
            position.updated_at = datetime.utcnow()
        else:
            position = Position(
                symbol=symbol, shares=shares, avg_cost=price,
                created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
            )
            db.add(position)

        trade = Trade(
            symbol=symbol, action="buy", shares=shares, price=price,
            total_amount=total, reason=reason, ai_score=score,
            executed_at=datetime.utcnow(),
        )
        db.add(trade)
        db.commit()

        logger.info(f"BUY  {symbol}: {shares:.4f}株 @ {price:.2f} = ¥{total:,.0f}")
        return trade

    def sell(
        self,
        db: Session,
        symbol: str,
        price: float,
        reason: str = "",
        score: float = 0.0,
    ) -> Optional[Trade]:
        position = self.get_position(db, symbol)
        if not position or position.shares <= 0:
            logger.warning(f"SELL skip {symbol}: ポジションなし")
            return None

        shares       = position.shares
        total        = shares * price
        realized_pnl = (price - position.avg_cost) * shares

        balance            = self._ensure_cash(db)
        balance.amount    += total
        balance.updated_at = datetime.utcnow()

        trade = Trade(
            symbol=symbol, action="sell", shares=shares, price=price,
            total_amount=total, realized_pnl=realized_pnl,
            reason=reason, ai_score=score, executed_at=datetime.utcnow(),
        )
        db.add(trade)

        position.shares     = 0.0
        position.updated_at = datetime.utcnow()

        db.commit()

        logger.info(f"SELL {symbol}: {shares:.4f}株 @ {price:.2f} 実現損益 ¥{realized_pnl:+,.0f}")
        return trade

    def get_summary(self, db: Session, current_prices: dict | None = None) -> dict:
        cash = self._ensure_cash(db).amount
        positions = self.get_all_positions(db)

        total_market_value = 0.0
        positions_data: list[dict] = []

        for pos in positions:
            cp = (current_prices or {}).get(pos.symbol) or pos.avg_cost
            market_value  = pos.shares * cp
            cost_basis    = pos.shares * pos.avg_cost
            unrealized    = market_value - cost_basis
            unrealized_pct= unrealized / cost_basis * 100 if cost_basis > 0 else 0.0

            total_market_value += market_value
            positions_data.append(
                {
                    "symbol":         pos.symbol,
                    "shares":         pos.shares,
                    "avg_cost":       pos.avg_cost,
                    "current_price":  cp,
                    "market_value":   market_value,
                    "unrealized_pnl": unrealized,
                    "unrealized_pct": unrealized_pct,
                }
            )

        total_assets = cash + total_market_value
        total_pnl    = total_assets - settings.INITIAL_CAPITAL
        pnl_pct      = total_pnl / settings.INITIAL_CAPITAL * 100 if settings.INITIAL_CAPITAL > 0 else 0.0

        realized_pnl = sum(
            t.realized_pnl
            for t in db.query(Trade).filter(Trade.action == "sell").all()
            if t.realized_pnl is not None
        )

        return {
            "cash":               cash,
            "total_market_value": total_market_value,
            "total_assets":       total_assets,
            "total_pnl":          total_pnl,
            "pnl_pct":            pnl_pct,
            "realized_pnl":       realized_pnl,
            "positions":          positions_data,
        }
