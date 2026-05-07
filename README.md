# 📈 株AI仮想取引ダッシュボード

> AIがニュースを分析して売買シグナルを出す、仮想株式取引シミュレーター。

![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-FF4B4B?style=flat-square&logo=streamlit)
![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python)
![Claude](https://img.shields.io/badge/Claude-Haiku-8A2BE2?style=flat-square)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?style=flat-square&logo=openai)

> ⚠️ **本アプリは学習・検証用の仮想取引シミュレーターです。実際の投資助言ではありません。**

---

## ✨ 特徴

- **AIによる売買シグナル** — ニュースをAIが分析し、買い・売り・様子見を判定
- **日米株対応** — 日本株8銘柄・米国株10銘柄のウォッチリスト
- **リアルタイム株価** — yfinance による最新株価の取得
- **ニュース収集** — RSSフィードから各銘柄のニュースを自動収集
- **仮想ポートフォリオ管理** — 初期資金100万円でシミュレーション
- **取引履歴・損益グラフ** — Plotlyによるインタラクティブなチャート表示
- **AI プロバイダー切替** — Anthropic Claude / OpenAI GPT を設定で切り替え可能

---

## 🎯 ウォッチリスト

| 日本株 | 米国株 |
|---|---|
| トヨタ・ソニー・ソフトバンクG・任天堂 | Apple・Microsoft・Alphabet・Amazon |
| キーエンス・東京エレクトロン・NTT・キヤノン | NVIDIA・Meta・Tesla・JPMorgan・Visa・J&J |

---

## 🛠️ 技術スタック

| カテゴリ | 技術 |
|---|---|
| UI | Streamlit |
| AI分析 | Anthropic Claude / OpenAI GPT |
| 株価データ | yfinance |
| ニュース収集 | feedparser（RSSフィード） |
| データベース | SQLite + SQLAlchemy |
| グラフ | Plotly |

---

## 📁 ディレクトリ構成

```
kabu-trader/
├── app.py               # Streamlitメインアプリ
├── ai_analyzer.py       # AI分析エンジン
├── market_data.py       # 株価データ取得
├── news_collector.py    # ニュース収集
├── portfolio.py         # ポートフォリオ管理
├── trading_engine.py    # 売買ロジック
├── database.py          # DBモデル
├── config.py            # 設定・ウォッチリスト
├── scheduler_job.py     # 定期実行ジョブ
├── requirements.txt
└── .env.example         # 環境変数テンプレート
```

---

## 🚀 セットアップ

```bash
# 1. クローン
git clone https://github.com/masafykun/kabu-trader.git
cd kabu-trader

# 2. 仮想環境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. 環境変数
cp .env.example .env
# .env にAPIキーを記入

# 4. 起動
streamlit run app.py
```

---

## 🔑 環境変数

`.env.example` をコピーして `.env` を作成してください。

| 変数名 | 説明 |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic APIキー（Claude使用時） |
| `OPENAI_API_KEY` | OpenAI APIキー（GPT使用時） |
| `AI_PROVIDER` | 使用するAI（`anthropic` または `openai`） |
| `INITIAL_CAPITAL` | 仮想ポートフォリオの初期資金（デフォルト: 1,000,000円） |
| `BUY_THRESHOLD` | 買いシグナルの閾値（デフォルト: 65） |
| `SELL_THRESHOLD` | 売りシグナルの閾値（デフォルト: 35） |

---

## 📜 ライセンス

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)

このプロジェクトは **MIT ライセンス** のもとで公開しています。
使用・参考にした際はできる限り作者へのクレジット表記をお願いします。

```
© 2025 masafykun (https://github.com/masafykun)
```
