"""
뉴스 수집 및 필터링 모듈
Google News RSS를 requests + ElementTree로 직접 파싱하여
feedparser / sgmllib3k 의존성 없이 동작한다.
"""

import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

# 수집할 검색 키워드
RSS_KEYWORDS = ["AI automation", "LLM", "developer"]

# 필터링 키워드 (제목 기준)
FILTER_KEYWORDS = ["AI", "automation", "LLM", "developer", "API"]

# Google News RSS URL 템플릿
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

MAX_ARTICLES_PER_KEYWORD = 10

# RSS 네임스페이스
_NS = {"media": "http://search.yahoo.com/mrss/"}


def build_rss_url(keyword: str) -> str:
    encoded = requests.utils.quote(keyword)
    return GOOGLE_NEWS_RSS.format(query=encoded)


def fetch_news_by_keyword(keyword: str, max_count: int = MAX_ARTICLES_PER_KEYWORD) -> list[dict]:
    """단일 키워드로 RSS 뉴스 수집"""
    url = build_rss_url(keyword)
    logger.info(f"뉴스 수집 중: keyword='{keyword}'")

    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        articles = _parse_rss(resp.text, keyword, max_count)
        logger.info(f"'{keyword}' 키워드로 {len(articles)}개 수집 완료")
        return articles
    except requests.RequestException as e:
        logger.error(f"뉴스 수집 실패 (keyword='{keyword}'): {e}")
        return []


def fetch_all_news(max_per_keyword: int = MAX_ARTICLES_PER_KEYWORD) -> list[dict]:
    """전체 키워드 수집 후 메모리 내 중복 제거"""
    all_articles: list[dict] = []
    seen_ids: set[str] = set()

    for keyword in RSS_KEYWORDS:
        for article in fetch_news_by_keyword(keyword, max_per_keyword):
            if article["id"] not in seen_ids:
                seen_ids.add(article["id"])
                all_articles.append(article)

    logger.info(f"총 {len(all_articles)}개 뉴스 수집 완료 (중복 제거 후)")
    return all_articles


def filter_news(articles: list[dict]) -> list[dict]:
    """제목 기준 키워드 필터링"""
    filtered = [
        a for a in articles
        if any(kw.lower() in a["title"].lower() for kw in FILTER_KEYWORDS)
    ]
    logger.info(f"필터링 결과: {len(articles)}개 → {len(filtered)}개")
    return filtered


def deduplicate_with_redis(articles: list[dict], redis_client) -> list[dict]:
    """Redis를 활용한 7일 TTL 중복 제거"""
    new_articles = []
    for article in articles:
        key = f"insta_news:seen:{article['id']}"
        if not redis_client.exists(key):
            redis_client.setex(key, 604800, "1")
            new_articles.append(article)
    logger.info(f"Redis 중복 제거: {len(articles)}개 → {len(new_articles)}개")
    return new_articles


def format_for_prompt(articles: list[dict], max_articles: int = 5) -> str:
    """Claude 프롬프트용 뉴스 텍스트 포맷팅"""
    lines = []
    for i, article in enumerate(articles[:max_articles], 1):
        lines.append(f"{i}. 제목: {article['title']}")
        if article["summary"]:
            lines.append(f"   요약: {article['summary'][:200]}")
        lines.append(f"   출처: {article['source']}")
        lines.append("")
    return "\n".join(lines)


# ── 내부 파싱 헬퍼 ────────────────────────────────────────────────────────────

def _parse_rss(xml_text: str, keyword: str, max_count: int) -> list[dict]:
    """RSS XML 텍스트를 파싱하여 기사 리스트 반환"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.error(f"RSS XML 파싱 실패: {e}")
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    articles = []
    for item in list(channel.findall("item"))[:max_count]:
        title = _tag_text(item, "title")
        link = _tag_text(item, "link")
        summary = _clean_html(_tag_text(item, "description"))
        published = _tag_text(item, "pubDate")
        source_el = item.find("source")
        source = source_el.text if source_el is not None else "Unknown"

        articles.append({
            "title": title,
            "summary": summary,
            "link": link,
            "published": published,
            "source": source,
            "keyword": keyword,
            "id": _make_id(title, link),
        })

    return articles


def _tag_text(element: ET.Element, tag: str) -> str:
    el = element.find(tag)
    return (el.text or "").strip() if el is not None else ""


def _clean_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", clean).strip()


def _make_id(title: str, link: str) -> str:
    return hashlib.md5(f"{title}::{link}".encode()).hexdigest()
