import json
import logging
import re
import time
from datetime import datetime

from config import settings
from database import NewsArticle

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "あなたは金融ニュース分析の専門家です。ニュース記事を分析してJSON形式のみで回答します。余分なテキストは不要です。"

ANALYSIS_TEMPLATE = """以下のニュース記事を分析してください。

タイトル: {title}
本文: {content}

以下のJSON形式のみで回答してください:
{{
  "summary": "記事の要約（日本語、100字以内）",
  "sentiment": "positive または negative または neutral",
  "sentiment_score": -1.0から1.0の数値,
  "related_symbols": ["関連銘柄コード例: AAPL, 7203.T"],
  "importance_score": 0から100の整数,
  "price_impact": "上昇 または 下落 または 中立",
  "reason": "株価への影響判断理由（日本語、50字以内）"
}}"""


class AIAnalyzer:
    def __init__(self):
        self._anthropic = None
        self._openai = None

        if settings.ANTHROPIC_API_KEY:
            try:
                import anthropic
                self._anthropic = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            except ImportError:
                logger.warning("anthropic package not installed")

        if not self._anthropic and settings.OPENAI_API_KEY:
            try:
                import openai
                self._openai = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            except ImportError:
                logger.warning("openai package not installed")

    @property
    def is_available(self) -> bool:
        return self._anthropic is not None or self._openai is not None

    def _parse_json(self, text: str) -> dict | None:
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except Exception:
                    pass
        logger.error(f"JSON parse failed: {text[:200]}")
        return None

    def analyze_article(self, title: str, content: str) -> dict | None:
        if not self.is_available:
            return None

        prompt = ANALYSIS_TEMPLATE.format(title=title, content=content[:1500])

        try:
            if self._anthropic:
                resp = self._anthropic.messages.create(
                    model=settings.AI_MODEL_ANTHROPIC,
                    max_tokens=512,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = resp.content[0].text
            else:
                resp = self._openai.chat.completions.create(
                    model=settings.AI_MODEL_OPENAI,
                    max_tokens=512,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                )
                text = resp.choices[0].message.content

            return self._parse_json(text)

        except Exception as e:
            logger.error(f"AI analyze error: {e}")
            return None

    def analyze_pending(self, db, limit: int = 20) -> int:
        pending = (
            db.query(NewsArticle)
            .filter(NewsArticle.ai_analysis == None)  # noqa: E711
            .order_by(NewsArticle.created_at.desc())
            .limit(limit)
            .all()
        )

        count = 0
        for article in pending:
            result = self.analyze_article(article.title, article.summary or "")
            if not result:
                continue

            article.summary         = result.get("summary", "")
            article.sentiment       = result.get("sentiment", "neutral")
            article.sentiment_score = float(result.get("sentiment_score", 0.0))
            article.importance_score= float(result.get("importance_score", 50))
            article.ai_analysis     = json.dumps(result, ensure_ascii=False)

            # AI が発見した追加銘柄をマージ
            current    = json.loads(article.related_symbols or "[]")
            ai_symbols = result.get("related_symbols", [])
            merged     = list(dict.fromkeys(current + [s for s in ai_symbols if isinstance(s, str)]))
            article.related_symbols = json.dumps(merged)

            count += 1
            time.sleep(0.3)  # レート制限

        if count > 0:
            db.commit()
        return count
