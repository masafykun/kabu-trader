import os
from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

os.makedirs("/root/kabu-trader/data", exist_ok=True)

DATABASE_URL = "sqlite:////root/kabu-trader/data/kabu_trader.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id              = Column(Integer, primary_key=True, index=True)
    title           = Column(Text, nullable=False)
    url             = Column(String(2048), unique=True, nullable=False)
    source          = Column(String(255))
    published_at    = Column(DateTime)
    fetched_at      = Column(DateTime, default=datetime.utcnow)
    summary         = Column(Text)
    sentiment       = Column(String(16))      # positive / negative / neutral
    sentiment_score = Column(Float)           # -1.0 ~ 1.0
    related_symbols = Column(Text)            # JSON array string
    importance_score= Column(Float)           # 0 ~ 100
    ai_analysis     = Column(Text)            # JSON string
    created_at      = Column(DateTime, default=datetime.utcnow)


class Trade(Base):
    __tablename__ = "trades"

    id           = Column(Integer, primary_key=True, index=True)
    symbol       = Column(String(32), nullable=False)
    action       = Column(String(8),  nullable=False)  # buy / sell
    shares       = Column(Float, nullable=False)
    price        = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    realized_pnl = Column(Float, nullable=True)        # sell 時のみ
    reason       = Column(Text)
    ai_score     = Column(Float)
    executed_at  = Column(DateTime, default=datetime.utcnow)


class Position(Base):
    __tablename__ = "positions"

    id         = Column(Integer, primary_key=True, index=True)
    symbol     = Column(String(32), unique=True, nullable=False)
    shares     = Column(Float, nullable=False, default=0)
    avg_cost   = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class CashBalance(Base):
    __tablename__ = "cash_balance"

    id         = Column(Integer, primary_key=True)
    amount     = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


class AISignal(Base):
    __tablename__ = "ai_signals"

    id             = Column(Integer, primary_key=True, index=True)
    symbol         = Column(String(32), nullable=False)
    action         = Column(String(8),  nullable=False)  # buy / sell / hold / wait
    score          = Column(Float)
    reason         = Column(Text)
    news_sentiment = Column(Float)
    price_trend    = Column(Float)
    volume_change  = Column(Float)
    current_price  = Column(Float)
    created_at     = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)
