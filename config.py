from pydantic_settings import BaseSettings
from typing import Dict, Any

WATCHLIST: Dict[str, Dict[str, Any]] = {
    # 日本株
    "7203.T": {"name": "トヨタ自動車",    "market": "JP", "query_ja": "トヨタ 株価",         "query_en": "Toyota TM stock"},
    "6758.T": {"name": "ソニーグループ",   "market": "JP", "query_ja": "ソニー 株価",          "query_en": "Sony SONY stock"},
    "9984.T": {"name": "ソフトバンクG",    "market": "JP", "query_ja": "ソフトバンク 株価",    "query_en": "SoftBank SFTBY stock"},
    "7974.T": {"name": "任天堂",           "market": "JP", "query_ja": "任天堂 株価",          "query_en": "Nintendo NTDOY stock"},
    "6861.T": {"name": "キーエンス",       "market": "JP", "query_ja": "キーエンス 株価",      "query_en": "Keyence stock"},
    "8035.T": {"name": "東京エレクトロン", "market": "JP", "query_ja": "東京エレクトロン 株価","query_en": "Tokyo Electron stock"},
    "9432.T": {"name": "NTT",              "market": "JP", "query_ja": "NTT 株価",             "query_en": "NTT Docomo stock"},
    "7751.T": {"name": "キヤノン",         "market": "JP", "query_ja": "キヤノン 株価",        "query_en": "Canon CAJ stock"},
    # 米国株
    "AAPL":  {"name": "Apple",     "market": "US", "query_ja": "アップル 株",      "query_en": "Apple AAPL stock"},
    "MSFT":  {"name": "Microsoft", "market": "US", "query_ja": "マイクロソフト 株","query_en": "Microsoft MSFT stock"},
    "GOOGL": {"name": "Alphabet",  "market": "US", "query_ja": "グーグル 株",      "query_en": "Alphabet GOOGL stock"},
    "AMZN":  {"name": "Amazon",    "market": "US", "query_ja": "アマゾン 株",      "query_en": "Amazon AMZN stock"},
    "NVDA":  {"name": "NVIDIA",    "market": "US", "query_ja": "エヌビディア 株",  "query_en": "NVIDIA NVDA stock"},
    "META":  {"name": "Meta",      "market": "US", "query_ja": "メタ 株",          "query_en": "Meta META stock"},
    "TSLA":  {"name": "Tesla",     "market": "US", "query_ja": "テスラ 株",        "query_en": "Tesla TSLA stock"},
    "JPM":   {"name": "JPMorgan",  "market": "US", "query_ja": "JPモルガン 株",    "query_en": "JPMorgan JPM stock"},
    "V":     {"name": "Visa",      "market": "US", "query_ja": "ビザ 株",          "query_en": "Visa V stock"},
    "JNJ":   {"name": "J&J",       "market": "US", "query_ja": "ジョンソン 株",    "query_en": "Johnson Johnson JNJ stock"},
}


class Settings(BaseSettings):
    APP_NAME: str = "株AI仮想取引ダッシュボード"
    DATABASE_URL: str = "sqlite:////root/kabu-trader/data/kabu_trader.db"

    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    AI_PROVIDER: str = "anthropic"
    AI_MODEL_ANTHROPIC: str = "claude-haiku-4-5-20251001"
    AI_MODEL_OPENAI: str = "gpt-4o-mini"

    INITIAL_CAPITAL: float = 1_000_000.0
    BUY_THRESHOLD: float = 65.0
    SELL_THRESHOLD: float = 35.0
    MAX_POSITION_PCT: float = 0.10  # ポジション当たり最大10%

    NEWS_PER_SYMBOL: int = 5

    model_config = {"env_file": "/root/kabu-trader/.env", "extra": "ignore"}


settings = Settings()
