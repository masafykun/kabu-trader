#!/usr/bin/env python3
"""
株AI仮想取引 自動スケジューラー

systemd timer から15分ごとに呼び出される。
スクリプト自身が市場時間を判定し、必要な間隔が経過していない場合はスキップする。

実行間隔:
  JP市場 (9:00-15:30 JST 平日)   : 15分
  US市場 (22:00-6:00  JST 平日)   : 15分
  平日オフ時間                     : 120分
  週末・祝日                       : 360分
"""
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import exchange_calendars as xcals

os.chdir("/root/kabu-trader")
sys.path.insert(0, "/root/kabu-trader")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
LAST_RUN_FILE = "/root/kabu-trader/data/last_scheduler_run.json"

# 実行間隔 (分)
INTERVAL_MARKET  = 15   # 市場開場中
INTERVAL_WEEKDAY = 120  # 平日・祝日の閉場時間帯
INTERVAL_HOLIDAY = 360  # 週末・連休

# 東証・NYSE カレンダー (モジュール読み込み時に一度だけ初期化)
_TSE  = xcals.get_calendar("XTKS")  # 東京証券取引所
_NYSE = xcals.get_calendar("XNYS")  # ニューヨーク証券取引所


# ─── 市場時間判定 (祝日対応) ────────────────────────────────────────────────────

def is_jp_market_open(now: datetime) -> bool:
    """東証セッション日かつ 9:00-15:30 JST"""
    if not _TSE.is_session(str(now.date())):
        return False
    t = (now.hour, now.minute)
    return (9, 0) <= t < (15, 30)


def is_us_market_open(now: datetime) -> bool:
    """NYSE セッション日かつ 22:00-翌6:00 JST (夏冬時間どちらもカバー)"""
    t = (now.hour, now.minute)
    # 22:00以降 → 当日ET日付と一致, 06:00未満 → 前日ET日付と一致
    if t >= (22, 0):
        nyse_date = now.date()
    elif t < (6, 0):
        nyse_date = (now - timedelta(days=1)).date()
    else:
        return False
    return _NYSE.is_session(str(nyse_date))


def _is_any_market_day(now: datetime) -> bool:
    """今日が東証またはNYSEの営業日か（時間帯不問）"""
    # NYSE は前日夜から今朝にかけて開いているので前日も確認
    return (
        _TSE.is_session(str(now.date()))
        or _NYSE.is_session(str(now.date()))
        or _NYSE.is_session(str((now - timedelta(days=1)).date()))
    )


def required_interval(now: datetime) -> int:
    if is_jp_market_open(now) or is_us_market_open(now):
        return INTERVAL_MARKET
    if _is_any_market_day(now):
        return INTERVAL_WEEKDAY
    return INTERVAL_HOLIDAY


# ─── 前回実行管理 ─────────────────────────────────────────────────────────────

def load_last_run() -> dict:
    try:
        with open(LAST_RUN_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_last_run(data: dict):
    os.makedirs(os.path.dirname(LAST_RUN_FILE), exist_ok=True)
    with open(LAST_RUN_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def should_run(now: datetime) -> tuple[bool, str]:
    """(実行すべきか, 理由メッセージ)"""
    last = load_last_run()
    last_run_str = last.get("last_run")

    if not last_run_str:
        return True, "初回実行"

    last_time = datetime.fromisoformat(last_run_str)
    if last_time.tzinfo is None:
        last_time = last_time.replace(tzinfo=JST)

    elapsed = (now - last_time).total_seconds() / 60
    interval = required_interval(now)

    if elapsed >= interval:
        return True, f"前回から {elapsed:.0f}分経過 (必要: {interval}分)"
    return False, f"スキップ: 前回から {elapsed:.0f}分 / 必要 {interval}分"


# ─── 分析・売買実行 ───────────────────────────────────────────────────────────

def run_analysis(now: datetime) -> dict:
    from ai_analyzer import AIAnalyzer
    from database import SessionLocal, init_db
    from news_collector import NewsCollector
    from trading_engine import TradingEngine

    init_db()
    conn = SessionLocal()
    result = {"news": 0, "analyzed": 0, "signals": 0, "trades": 0}

    try:
        result["news"] = NewsCollector().collect_all(conn)
        logger.info(f"ニュース収集: {result['news']}件")

        ai = AIAnalyzer()
        if ai.is_available:
            result["analyzed"] = ai.analyze_pending(conn)
            logger.info(f"AI分析: {result['analyzed']}件")
        else:
            logger.warning("AI APIキー未設定 — ニュース感情分析をスキップ")

        engine = TradingEngine()
        signals = engine.generate_all_signals(conn)
        result["signals"] = len(signals)
        logger.info(f"シグナル生成: {result['signals']}件")

        result["trades"] = engine.execute_signals(conn, signals)
        logger.info(f"自動売買: {result['trades']}件約定")

    except Exception as e:
        logger.error(f"分析エラー: {e}", exc_info=True)
        result["error"] = str(e)
    finally:
        conn.close()

    return result


# ─── エントリーポイント ───────────────────────────────────────────────────────

def main():
    now = datetime.now(JST)
    jp_open = is_jp_market_open(now)
    us_open = is_us_market_open(now)
    interval = required_interval(now)

    logger.info(
        f"起動: {now.strftime('%Y/%m/%d %H:%M %Z')} | "
        f"JP={'開場' if jp_open else '閉場'} | "
        f"US={'開場' if us_open else '閉場'} | "
        f"設定間隔={interval}分"
    )

    ok, msg = should_run(now)
    logger.info(msg)

    if not ok:
        return  # 間隔未達のため終了

    logger.info("===== 分析・売買開始 =====")
    result = run_analysis(now)
    logger.info(
        f"===== 完了 ===== "
        f"ニュース{result['news']}件 / "
        f"分析{result['analyzed']}件 / "
        f"シグナル{result['signals']}件 / "
        f"約定{result['trades']}件"
    )

    save_last_run({
        "last_run": now.isoformat(),
        "jp_open": jp_open,
        "us_open": us_open,
        "interval_minutes": interval,
        **result,
    })


if __name__ == "__main__":
    main()
