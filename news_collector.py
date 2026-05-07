import json
import logging
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode

import feedparser

from config import settings, WATCHLIST
from database import NewsArticle

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


class NewsCollector:
    def _build_url(self, query: str, market: str) -> str:
        if market == "JP":
            params = urlencode({"q": query, "hl": "ja", "gl": "JP", "ceid": "JP:ja"})
        else:
            params = urlencode({"q": query, "hl": "en", "gl": "US", "ceid": "US:en"})
        return f"{GOOGLE_NEWS_RSS}?{params}"

    def _parse_date(self, entry) -> datetime:
        try:
            dt = parsedate_to_datetime(entry.get("published", ""))
            return dt.replace(tzinfo=None)
        except Exception:
            return datetime.utcnow()

    def _fetch_rss(self, url: str) -> list[dict]:
        try:
            feed = feedparser.parse(url)
            articles = []
            for entry in feed.entries[: settings.NEWS_PER_SYMBOL]:
                source = ""
                if hasattr(entry, "source"):
                    source = getattr(entry.source, "title", "")

                articles.append(
                    {
                        "title": entry.get("title", ""),
                        "url": entry.get("link", ""),
                        "source": source,
                        "published_at": self._parse_date(entry),
                        "content": entry.get("summary", ""),
                    }
                )
            return articles
        except Exception as e:
            logger.error(f"RSS fetch error ({url}): {e}")
            return []

    def collect_for_symbol(self, symbol: str, db) -> int:
        if symbol not in WATCHLIST:
            return 0

        info = WATCHLIST[symbol]
        market = info.get("market", "US")
        query = info["query_ja"] if market == "JP" else info["query_en"]
        url = self._build_url(query, market)

        articles = self._fetch_rss(url)
        count = 0

        for article in articles:
            if not article["url"]:
                continue
            existing = db.query(NewsArticle).filter(NewsArticle.url == article["url"]).first()
            if existing:
                # 銘柄を関連リストに追加
                current = json.loads(existing.related_symbols or "[]")
                if symbol not in current:
                    current.append(symbol)
                    existing.related_symbols = json.dumps(current)
                continue

            news = NewsArticle(
                title=article["title"],
                url=article["url"],
                source=article["source"],
                published_at=article["published_at"],
                fetched_at=datetime.utcnow(),
                related_symbols=json.dumps([symbol]),
            )
            db.add(news)
            count += 1

        if count > 0:
            db.commit()
        return count

    def collect_all(self, db) -> int:
        total = 0
        for symbol in WATCHLIST:
            try:
                count = self.collect_for_symbol(symbol, db)
                total += count
                time.sleep(0.3)
            except Exception as e:
                logger.error(f"Collect error ({symbol}): {e}")
        return total
