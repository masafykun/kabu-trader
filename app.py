"""
株AI仮想取引ダッシュボード
※ 本アプリは学習・検証用の仮想取引シミュレーターです。実際の投資助言ではありません。
"""
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ai_analyzer import AIAnalyzer
from config import WATCHLIST, settings
from database import AISignal, NewsArticle, Trade, init_db
from database import SessionLocal as _SessionLocal
from market_data import MarketDataFetcher
from news_collector import NewsCollector
from portfolio import PortfolioManager
from trading_engine import TradingEngine

logging.basicConfig(level=logging.INFO)

# ─── ページ設定 ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="株AI仮想取引",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

# ─── コンポーネント (セッション間で再利用) ─────────────────────────────────────
@st.cache_resource
def _news_col():  return NewsCollector()
@st.cache_resource
def _ai_ana():    return AIAnalyzer()
@st.cache_resource
def _market():    return MarketDataFetcher()
@st.cache_resource
def _engine():    return TradingEngine()
@st.cache_resource
def _portfolio(): return PortfolioManager()


def db():
    return _SessionLocal()


ACTION_JP    = {"buy": "買い 🟢", "sell": "売り 🔴", "hold": "保有 🟡", "wait": "様子見 ⚪"}
SENT_BADGE   = {"positive": "🟢 ポジティブ", "negative": "🔴 ネガティブ", "neutral": "⚪ 中立"}
ACTION_COLOR = {"buy": "green", "sell": "red", "hold": "#ccaa00", "wait": "gray"}


# ─── 分析実行 ──────────────────────────────────────────────────────────────────
def run_analysis(auto_execute: bool) -> dict:
    conn = db()
    result = {"news": 0, "analyzed": 0, "signals": 0, "trades": 0, "error": None}
    try:
        prog = st.sidebar.progress(0, "ニュース収集中...")
        result["news"] = _news_col().collect_all(conn)
        prog.progress(33, "AI 分析中...")

        ai = _ai_ana()
        if ai.is_available:
            result["analyzed"] = ai.analyze_pending(conn)
        prog.progress(66, "シグナル生成中...")

        signals = _engine().generate_all_signals(conn)
        result["signals"] = len(signals)
        prog.progress(90, "売買判断中...")

        if auto_execute and signals:
            result["trades"] = _engine().execute_signals(conn, signals)
        prog.progress(100, "完了")
    except Exception as e:
        result["error"] = str(e)
        logging.exception("Analysis error")
    finally:
        conn.close()
    return result


# ─── スケジューラー状態表示 ───────────────────────────────────────────────────────
_JST = ZoneInfo("Asia/Tokyo")
_LAST_RUN_FILE = "/root/kabu-trader/data/last_scheduler_run.json"


@st.cache_resource
def _get_calendars():
    import exchange_calendars as xcals
    return xcals.get_calendar("XTKS"), xcals.get_calendar("XNYS")


def _is_jp_open(now: datetime) -> bool:
    tse, _ = _get_calendars()
    if not tse.is_session(str(now.date())):
        return False
    t = (now.hour, now.minute)
    return (9, 0) <= t < (15, 30)


def _is_us_open(now: datetime) -> bool:
    from datetime import timedelta
    _, nyse = _get_calendars()
    t = (now.hour, now.minute)
    if t >= (22, 0):
        nyse_date = now.date()
    elif t < (6, 0):
        nyse_date = (now - timedelta(days=1)).date()
    else:
        return False
    return nyse.is_session(str(nyse_date))


def _render_scheduler_status():
    now = datetime.now(_JST)
    jp = _is_jp_open(now)
    us = _is_us_open(now)

    market_str = []
    if jp: market_str.append("🇯🇵 JP開場中")
    if us: market_str.append("🇺🇸 US開場中")
    if not market_str:
        if now.weekday() >= 5:
            market_str.append("💤 週末")
        else:
            market_str.append("🌙 閉場中")

    st.sidebar.caption("🕐 **自動スケジューラー**")
    st.sidebar.caption(" / ".join(market_str))

    try:
        with open(_LAST_RUN_FILE) as f:
            data = json.load(f)
        last_dt = datetime.fromisoformat(data["last_run"])
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=_JST)
        elapsed = int((now - last_dt).total_seconds() / 60)
        st.sidebar.caption(
            f"前回実行: {last_dt.strftime('%m/%d %H:%M')} ({elapsed}分前)\n"
            f"N:{data.get('news',0)} / 分析:{data.get('analyzed',0)} / "
            f"約定:{data.get('trades',0)}"
        )
        tse, nyse = _get_calendars()
        from datetime import timedelta as _td
        any_market = (
            tse.is_session(str(now.date()))
            or nyse.is_session(str(now.date()))
            or nyse.is_session(str((now - _td(days=1)).date()))
        )
        interval = 15 if (jp or us) else (120 if any_market else 360)
        next_min = max(0, interval - elapsed)
        st.sidebar.caption(f"次回まで約 {next_min}分 (間隔:{interval}分)")
    except (FileNotFoundError, KeyError):
        st.sidebar.caption("まだ自動実行されていません")


# ─── サイドバー ─────────────────────────────────────────────────────────────────
def render_sidebar():
    st.sidebar.title("📈 株AI仮想取引")
    st.sidebar.caption("⚠️ 学習用仮想取引。実際の投資助言ではありません。")
    st.sidebar.divider()

    conn = db()
    try:
        pm   = _portfolio()
        cash = pm.get_cash(conn)
        pos  = pm.get_all_positions(conn)
        st.sidebar.metric("💴 現金残高", f"¥{cash:,.0f}")
        st.sidebar.metric("📦 保有銘柄", f"{len(pos)} 銘柄")
    finally:
        conn.close()

    st.sidebar.divider()
    col1, col2 = st.sidebar.columns([3, 2])
    run_btn    = col1.button("🔄 分析実行", use_container_width=True, type="primary")
    auto       = col2.checkbox("自動売買", value=False, key="auto_trade",
                               help="チェックするとシグナルに基づき自動的に仮想売買します")

    if run_btn:
        with st.sidebar:
            res = run_analysis(auto)
            if res["error"]:
                st.error(f"エラー: {res['error']}")
            else:
                msg = f"ニュース{res['news']}件 / 分析{res['analyzed']}件 / シグナル{res['signals']}件"
                if auto:
                    msg += f" / 約定{res['trades']}件"
                st.success(f"✅ 完了: {msg}")
        st.rerun()

    st.sidebar.caption(f"更新: {datetime.now().strftime('%m/%d %H:%M')}")
    ai = _ai_ana()
    if ai.is_available:
        st.sidebar.success("🤖 AI 利用可能")
    else:
        st.sidebar.warning("🤖 AI: .env に API キー未設定")

    # スケジューラー状態
    st.sidebar.divider()
    _render_scheduler_status()


# ─── タブ1: ダッシュボード ────────────────────────────────────────────────────
def tab_dashboard():
    conn = db()
    try:
        pm     = _portfolio()
        mf     = _market()
        pos    = pm.get_all_positions(conn)
        prices = {p.symbol: mf.get_current_price(p.symbol) for p in pos} if pos else {}
        summ   = pm.get_summary(conn, prices)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 総資産",    f"¥{summ['total_assets']:,.0f}",
                  delta=f"{summ['pnl_pct']:+.2f}%")
        c2.metric("💴 現金",      f"¥{summ['cash']:,.0f}")
        c3.metric("📊 投資評価額", f"¥{summ['total_market_value']:,.0f}")
        c4.metric("📈 損益",      f"¥{summ['total_pnl']:+,.0f}",
                  delta=f"{summ['pnl_pct']:+.2f}%",
                  delta_color="normal" if summ["total_pnl"] >= 0 else "inverse")

        st.divider()
        left, right = st.columns([3, 2])

        # 最新シグナル
        with left:
            st.subheader("🎯 最新シグナル")
            signals = (
                conn.query(AISignal)
                .order_by(AISignal.created_at.desc())
                .limit(10)
                .all()
            )
            if signals:
                for sig in signals:
                    name = WATCHLIST.get(sig.symbol, {}).get("name", sig.symbol)
                    with st.container(border=True):
                        a, b, c = st.columns([2, 1, 3])
                        a.write(f"**{name}** `{sig.symbol}`")
                        a.caption(sig.created_at.strftime("%m/%d %H:%M"))
                        b.write(ACTION_JP.get(sig.action, sig.action))
                        b.caption(f"スコア: **{sig.score:.0f}**")
                        if sig.reason:
                            c.caption(sig.reason[:100])
            else:
                st.info("シグナルがまだありません。サイドバーの「分析実行」を押してください。")

        # 注目銘柄ランキング
        with right:
            st.subheader("🔥 注目銘柄")
            cutoff  = datetime.utcnow() - timedelta(hours=48)
            recent  = (
                conn.query(NewsArticle)
                .filter(NewsArticle.created_at >= cutoff,
                        NewsArticle.ai_analysis != None)  # noqa
                .all()
            )
            sym_scores: dict[str, list[float]] = {}
            for a in recent:
                syms = json.loads(a.related_symbols or "[]")
                imp  = a.importance_score or 50.0
                for s in syms:
                    if s in WATCHLIST:
                        sym_scores.setdefault(s, []).append(imp)

            if sym_scores:
                ranked = sorted(
                    [(s, sum(v) / len(v)) for s, v in sym_scores.items()],
                    key=lambda x: x[1], reverse=True,
                )[:8]
                for sym, score in ranked:
                    name = WATCHLIST[sym]["name"]
                    icon = "🔥" if score >= 65 else "📰"
                    st.write(f"{icon} **{name}** `{sym}` — {score:.0f}点")
            else:
                st.info("データなし（分析実行後に表示されます）")

        # 損益推移グラフ
        st.divider()
        st.subheader("📉 実現損益の推移")
        trades = (
            conn.query(Trade)
            .filter(Trade.action == "sell", Trade.realized_pnl != None)  # noqa
            .order_by(Trade.executed_at)
            .all()
        )
        if trades:
            df = pd.DataFrame(
                [{"日時": t.executed_at, "実現損益": t.realized_pnl, "銘柄": t.symbol}
                 for t in trades]
            )
            df["累計損益"] = df["実現損益"].cumsum()
            fig = px.line(df, x="日時", y="累計損益", markers=True,
                          color_discrete_sequence=["#2196F3"])
            fig.update_layout(height=280, margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig, use_container_width=True, key="dashboard_pnl_chart")
        else:
            st.info("売買履歴がありません")
    finally:
        conn.close()


# ─── タブ2: ニュース分析 ──────────────────────────────────────────────────────
def tab_news():
    conn = db()
    try:
        sym_options = ["すべて"] + list(WATCHLIST.keys())
        col_filter, col_sort = st.columns([2, 1])
        selected_sym  = col_filter.selectbox("銘柄フィルター", sym_options, key="news_sym")
        show_analyzed = col_sort.checkbox("AI分析済みのみ", value=False, key="news_analyzed")

        q = conn.query(NewsArticle).order_by(NewsArticle.published_at.desc())
        if selected_sym != "すべて":
            q = q.filter(NewsArticle.related_symbols.contains(f'"{selected_sym}"'))
        if show_analyzed:
            q = q.filter(NewsArticle.ai_analysis != None)  # noqa
        articles = q.limit(50).all()

        st.caption(f"{len(articles)} 件表示中")
        st.divider()

        if not articles:
            st.info("ニュースがまだありません。分析実行でニュースを取得してください。")
            return

        for a in articles:
            with st.expander(f"{a.title[:80]}", expanded=False):
                col_meta, col_badge = st.columns([3, 1])
                col_meta.caption(
                    f"📰 {a.source or '不明'}　🕐 {a.published_at.strftime('%Y/%m/%d %H:%M') if a.published_at else ''}"
                )
                syms = json.loads(a.related_symbols or "[]")
                col_badge.write(" ".join(f"`{s}`" for s in syms[:5]))

                if a.ai_analysis:
                    analysis = json.loads(a.ai_analysis)
                    st.write(f"**要約:** {a.summary or '—'}")
                    col_s, col_i, col_p = st.columns(3)
                    col_s.info(SENT_BADGE.get(a.sentiment, a.sentiment or "—"))
                    col_i.metric("重要度", f"{a.importance_score:.0f}/100" if a.importance_score else "—")
                    col_p.write(f"**株価影響:** {analysis.get('price_impact', '—')}")
                    if analysis.get("reason"):
                        st.caption(f"💡 {analysis['reason']}")
                else:
                    st.caption("AI 分析未実施")

                st.markdown(f"[元記事を開く]({a.url})", unsafe_allow_html=False)
    finally:
        conn.close()


# ─── タブ3: ポートフォリオ ────────────────────────────────────────────────────
def tab_portfolio():
    conn = db()
    try:
        pm   = _portfolio()
        mf   = _market()
        pos  = pm.get_all_positions(conn)

        if pos:
            prices = {p.symbol: mf.get_current_price(p.symbol) for p in pos}
        else:
            prices = {}

        summ = pm.get_summary(conn, prices)

        c1, c2, c3 = st.columns(3)
        c1.metric("💰 総資産",   f"¥{summ['total_assets']:,.0f}")
        c2.metric("💴 現金",     f"¥{summ['cash']:,.0f}")
        c3.metric("✅ 実現損益", f"¥{summ['realized_pnl']:+,.0f}")

        st.divider()
        if summ["positions"]:
            rows = []
            for p in summ["positions"]:
                name = WATCHLIST.get(p["symbol"], {}).get("name", p["symbol"])
                rows.append({
                    "銘柄コード":   p["symbol"],
                    "銘柄名":       name,
                    "保有株数":     f"{p['shares']:.4f}",
                    "平均取得単価": f"¥{p['avg_cost']:,.2f}",
                    "現在値":       f"¥{p['current_price']:,.2f}",
                    "評価額":       f"¥{p['market_value']:,.0f}",
                    "含み損益":     f"¥{p['unrealized_pnl']:+,.0f}",
                    "損益率":       f"{p['unrealized_pct']:+.2f}%",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            # ポートフォリオ配分円グラフ
            labels = [f"{WATCHLIST.get(p['symbol'],{}).get('name', p['symbol'])}" for p in summ["positions"]]
            values = [p["market_value"] for p in summ["positions"]]
            labels.append("現金")
            values.append(summ["cash"])

            fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.4))
            fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig, use_container_width=True, key="portfolio_pie_chart")
        else:
            st.info("保有銘柄なし。シグナルで「自動売買」を有効にして分析を実行してください。")
    finally:
        conn.close()


# ─── タブ4: 取引シグナル ──────────────────────────────────────────────────────
def tab_signals():
    conn = db()
    try:
        cutoff  = datetime.utcnow() - timedelta(hours=24)
        signals = (
            conn.query(AISignal)
            .filter(AISignal.created_at >= cutoff)
            .order_by(AISignal.score.desc())
            .all()
        )

        if not signals:
            st.info("直近24時間のシグナルなし。分析実行してください。")
            return

        for sig in signals:
            name   = WATCHLIST.get(sig.symbol, {}).get("name", sig.symbol)
            market = WATCHLIST.get(sig.symbol, {}).get("market", "")
            color  = ACTION_COLOR.get(sig.action, "gray")

            with st.container(border=True):
                head_l, head_r = st.columns([3, 1])
                head_l.write(f"### {name} `{sig.symbol}` {'🇯🇵' if market=='JP' else '🇺🇸'}")
                head_r.markdown(
                    f"<span style='color:{color};font-size:1.3em;font-weight:bold'>"
                    f"{ACTION_JP.get(sig.action, sig.action)}</span>",
                    unsafe_allow_html=True,
                )

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("総合スコア",   f"{sig.score:.1f}")
                c2.metric("ニュース感情", f"{sig.news_sentiment:.1f}" if sig.news_sentiment else "—")
                c3.metric("価格トレンド", f"{sig.price_trend:.1f}"    if sig.price_trend    else "—")
                c4.metric("出来高スコア", f"{sig.volume_change:.1f}"  if sig.volume_change  else "—")

                if sig.current_price:
                    st.caption(f"現在値: ¥{sig.current_price:,.2f}　{sig.created_at.strftime('%m/%d %H:%M')}")
                if sig.reason:
                    st.caption(f"💡 判断理由: {sig.reason}")

                # スコアバー
                fig = go.Figure(go.Bar(
                    x=["感情", "価格", "出来高"],
                    y=[sig.news_sentiment or 50, sig.price_trend or 50, sig.volume_change or 50],
                    marker_color=["#2196F3", "#4CAF50", "#FF9800"],
                ))
                fig.add_hline(y=settings.BUY_THRESHOLD,  line_dash="dot", line_color="green", annotation_text="買いライン")
                fig.add_hline(y=settings.SELL_THRESHOLD, line_dash="dot", line_color="red",   annotation_text="売りライン")
                fig.update_layout(height=180, margin=dict(l=0, r=0, t=10, b=0),
                                  yaxis=dict(range=[0, 100]))
                st.plotly_chart(fig, use_container_width=True, key=f"signal_bar_{sig.id}")
    finally:
        conn.close()


# ─── タブ5: 売買履歴 ──────────────────────────────────────────────────────────
def tab_history():
    conn = db()
    try:
        trades = conn.query(Trade).order_by(Trade.executed_at.desc()).limit(200).all()

        if not trades:
            st.info("売買履歴なし")
            return

        rows = []
        for t in trades:
            name = WATCHLIST.get(t.symbol, {}).get("name", t.symbol)
            rows.append({
                "日時":       t.executed_at.strftime("%Y/%m/%d %H:%M"),
                "銘柄":       f"{name} ({t.symbol})",
                "売買":       "買い" if t.action == "buy" else "売り",
                "株数":       f"{t.shares:.4f}",
                "単価":       f"¥{t.price:,.2f}",
                "金額":       f"¥{t.total_amount:,.0f}",
                "実現損益":   f"¥{t.realized_pnl:+,.0f}" if t.realized_pnl is not None else "—",
                "AIスコア":   f"{t.ai_score:.1f}" if t.ai_score else "—",
                "理由":       (t.reason or "")[:40],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # 実現損益サマリー
        sell_trades = [t for t in trades if t.action == "sell" and t.realized_pnl is not None]
        if sell_trades:
            total_pnl = sum(t.realized_pnl for t in sell_trades)
            wins  = sum(1 for t in sell_trades if t.realized_pnl > 0)
            total = len(sell_trades)
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("実現損益合計", f"¥{total_pnl:+,.0f}")
            c2.metric("勝率",         f"{wins/total*100:.1f}%" if total > 0 else "—")
            c3.metric("取引回数(売)",  f"{total} 回")
    finally:
        conn.close()


# ─── メイン ───────────────────────────────────────────────────────────────────
render_sidebar()

st.title("📈 株AI仮想取引ダッシュボード")
st.caption(
    "⚠️ **免責事項:** 本アプリは学習・検証目的の仮想取引シミュレーターです。"
    " AIの判断は必ずしも正確ではなく、実際の投資判断の根拠として使用しないでください。"
)

t1, t2, t3, t4, t5 = st.tabs(
    ["📊 ダッシュボード", "📰 ニュース分析", "💼 ポートフォリオ", "🎯 取引シグナル", "📋 売買履歴"]
)

with t1: tab_dashboard()
with t2: tab_news()
with t3: tab_portfolio()
with t4: tab_signals()
with t5: tab_history()
