"""
뉴스 수집 및 필터링 모듈
Google News RSS를 통해 AI/개발자 관련 뉴스를 수집하고 필터링한다.
"""

import logging
import hashlib
import re
from datetime import datetime
from typing import Optional

import feedparser
import requests

logger = logging.getLogger(__name__)

# 수집할 검색 키워드
RSS_KEYWORDS = ["AI automation", "LLM", "developer"]

# 필터링 키워드 (제목 기준)
FILTER_KEYWORDS = ["AI", "automation", "LLM", "developer", "API"]

# Google News RSS URL 템플릿
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

# 수집 최대 개수
MAX_ARTICLES_PER_KEYWORD = 10


def build_rss_url(keyword: str) -> str:
    """키워드로 Google News RSS URL 생성"""
    encoded = requests.utils.quote(keyword)
    return GOOGLE_NEWS_RSS.format(query=encoded)


def fetch_news_by_keyword(keyword: str, max_count: int = MAX_ARTICLES_PER_KEYWORD) -> list[dict]:
    """
    단일 키워드로 RSS 뉴스 수집

    Args:
        keyword: 검색 키워드
        max_count: 최대 수집 개수

    Returns:
        뉴스 항목 리스트 (dict: title, summary, link, published, source)
    """
    url = build_rss_url(keyword)
    logger.info(f"뉴스 수집 중: keyword='{keyword}', url={url}")

    try:
        feed = feedparser.parse(url)
        articles = []

        for entry in feed.entries[:max_count]:
            article = {
                "title": entry.get("title", "").strip(),
                "summary": _clean_html(entry.get("summary", "")),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "source": entry.get("source", {}).get("title", "Unknown"),
                "keyword": keyword,
                "id": _make_article_id(entry.get("title", ""), entry.get("link", "")),
            }
            articles.append(article)

        logger.info(f"'{keyword}' 키워드로 {len(articles)}개 수집 완료")
        return articles

    except Exception as e:
        logger.error(f"뉴스 수집 실패 (keyword='{keyword}'): {e}")
        return []


def fetch_all_news(max_per_keyword: int = MAX_ARTICLES_PER_KEYWORD) -> list[dict]:
    """
    전체 키워드로 뉴스 수집 후 중복 제거

    Returns:
        중복 제거된 뉴스 리스트
    """
    all_articles: list[dict] = []
    seen_ids: set[str] = set()

    for keyword in RSS_KEYWORDS:
        articles = fetch_news_by_keyword(keyword, max_per_keyword)
        for article in articles:
            if article["id"] not in seen_ids:
                seen_ids.add(article["id"])
                all_articles.append(article)

    logger.info(f"총 {len(all_articles)}개 뉴스 수집 완료 (중복 제거 후)")
    return all_articles


def filter_news(articles: list[dict]) -> list[dict]:
    """
    제목 기준 키워드 필터링

    Args:
        articles: 뉴스 리스트

    Returns:
        필터링된 뉴스 리스트
    """
    filtered = []

    for article in articles:
        title_lower = article["title"].lower()
        if any(kw.lower() in title_lower for kw in FILTER_KEYWORDS):
            filtered.append(article)

    logger.info(f"필터링 결과: {len(articles)}개 → {len(filtered)}개")
    return filtered


def deduplicate_with_redis(articles: list[dict], redis_client) -> list[dict]:
    """
    Redis를 활용한 뉴스 중복 제거 (선택적 기능)

    Args:
        articles: 뉴스 리스트
        redis_client: Redis 클라이언트 (redis.Redis 인스턴스)

    Returns:
        중복 제거된 뉴스 리스트
    """
    new_articles = []
    key_prefix = "insta_news:seen:"

    for article in articles:
        redis_key = f"{key_prefix}{article['id']}"
        if not redis_client.exists(redis_key):
            # 7일(604800초) TTL로 저장
            redis_client.setex(redis_key, 604800, "1")
            new_articles.append(article)

    logger.info(f"Redis 중복 제거: {len(articles)}개 → {len(new_articles)}개")
    return new_articles


def format_for_prompt(articles: list[dict], max_articles: int = 5) -> str:
    """
    Claude 프롬프트용 뉴스 텍스트 포맷팅

    Args:
        articles: 뉴스 리스트
        max_articles: 프롬프트에 포함할 최대 기사 수

    Returns:
        포맷팅된 텍스트
    """
    lines = []
    for i, article in enumerate(articles[:max_articles], 1):
        lines.append(f"{i}. 제목: {article['title']}")
        if article["summary"]:
            lines.append(f"   요약: {article['summary'][:200]}")
        lines.append(f"   출처: {article['source']}")
        lines.append("")

    return "\n".join(lines)


def _clean_html(text: str) -> str:
    """HTML 태그 제거"""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _make_article_id(title: str, link: str) -> str:
    """기사 고유 ID 생성 (제목 + URL 해시)"""
    raw = f"{title}::{link}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()
