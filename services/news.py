"""
뉴스 수집 및 필터링 모듈
Google News RSS를 requests + ElementTree로 직접 파싱하여
feedparser / sgmllib3k 의존성 없이 동작한다.
"""

import hashlib
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# 수집할 검색 키워드
RSS_KEYWORDS = ["AI automation", "LLM", "developer"]

# 필터링 키워드 (제목 기준)
FILTER_KEYWORDS = ["AI", "automation", "LLM", "developer", "API"]

# Google News RSS URL 템플릿
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

MAX_ARTICLES_PER_KEYWORD = 10

# 수집 이력 캐시 파일 경로 및 TTL
SEEN_CACHE_PATH = "data/seen_articles.json"
CACHE_TTL_DAYS  = 30

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


def fetch_all_news(
    max_per_keyword: int = MAX_ARTICLES_PER_KEYWORD,
    cache_path: str = SEEN_CACHE_PATH,
) -> list[dict]:
    """전체 키워드 수집 후 파일 기반 중복 제거

    이전 실행에서 카드로 제작된 기사(mark_articles_as_seen으로 등록된 것)만 제외한다.
    수집 시점에는 캐시를 쓰지 않으므로, 하루에 여러 번 실행해도 새 기사를 수집할 수 있다.
    """
    seen_cache = _load_seen_cache(cache_path)
    seen_ids   = set(seen_cache.keys())

    all_articles: list[dict] = []
    this_run_ids: set[str]   = set()  # 이번 실행 내 중복 방지

    for keyword in RSS_KEYWORDS:
        for article in fetch_news_by_keyword(keyword, max_per_keyword):
            aid = article["id"]
            if aid not in seen_ids and aid not in this_run_ids:
                this_run_ids.add(aid)
                all_articles.append(article)

    logger.info(
        f"총 {len(all_articles)}개 신규 뉴스 수집 완료 "
        f"(이미 사용된 기사 {len(seen_ids)}개 제외)"
    )
    return all_articles


def mark_articles_as_seen(
    articles: list[dict],
    cache_path: str = SEEN_CACHE_PATH,
) -> None:
    """카드 생성에 실제 사용된 기사를 seen 캐시에 등록한다.

    fetch_all_news가 아닌 이 함수에서만 캐시를 기록하므로,
    카드로 만든 기사만 이후 실행에서 제외된다.
    """
    if not articles:
        return
    seen_cache = _load_seen_cache(cache_path)
    now = datetime.now().isoformat()
    for article in articles:
        seen_cache[article["id"]] = now
    _save_seen_cache(seen_cache, cache_path)
    logger.info(f"{len(articles)}개 기사를 seen 캐시에 등록")


# ── 파일 기반 중복 제거 캐시 ─────────────────────────────────────────────────

def _load_seen_cache(cache_path: str) -> dict[str, str]:
    """seen_articles.json 로드. 없거나 손상된 경우 빈 dict 반환."""
    path = Path(cache_path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"캐시 로드 실패, 초기화합니다: {e}")
        return {}


def _save_seen_cache(seen: dict[str, str], cache_path: str) -> None:
    """seen_articles.json 저장. TTL(30일) 초과 항목은 자동 삭제."""
    cutoff = datetime.now() - timedelta(days=CACHE_TTL_DAYS)
    cleaned = {
        k: v for k, v in seen.items()
        if datetime.fromisoformat(v) > cutoff
    }

    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"캐시 저장 완료: {len(cleaned)}개 항목 ({cache_path})")


def filter_news(articles: list[dict]) -> list[dict]:
    """제목 기준 키워드 필터링"""
    filtered = [
        a for a in articles
        if any(kw.lower() in a["title"].lower() for kw in FILTER_KEYWORDS)
    ]
    logger.info(f"필터링 결과: {len(articles)}개 → {len(filtered)}개")
    return filtered


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
