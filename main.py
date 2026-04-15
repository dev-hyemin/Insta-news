"""
AI 자동화 뉴스 콘텐츠 생성 시스템 - 메인 실행 파일

실행 흐름:
  1. 뉴스 수집 (Google News RSS)
  2. 키워드 필터링
  3. Claude API로 콘텐츠 생성
  4. 결과 파싱
  5. 카드 이미지 생성 (OUTPUT_DIR/{title}/ 하위에 저장)

사용 방법:
  python main.py
"""

import logging
import os
import sys
from datetime import date

from dotenv import load_dotenv

load_dotenv()

# ── 로깅 설정 ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── 서비스 임포트 ─────────────────────────────────────────────────────────────
from services.news import fetch_all_news, filter_news, format_for_prompt, mark_articles_as_seen
from services.claude import generate_content
from services.render import render_cards, save_description


def load_env() -> dict:
    """환경변수 로드 및 유효성 검사"""
    config = {
        "claude_api_key": os.getenv("CLAUDE_API_KEY", ""),
        "output_dir": os.getenv("OUTPUT_DIR", "output"),
    }

    if not config["claude_api_key"]:
        logger.error("필수 환경변수 누락: CLAUDE_API_KEY")
        logger.error(".env 파일에 CLAUDE_API_KEY를 설정하세요.")
        sys.exit(1)

    return config


def make_output_subdir(base_dir: str, title: str) -> str:
    """
    {base_dir}/{date}_{safe_title} 형태의 서브디렉토리 경로 반환

    예) output/2026-04-15_AI_automation_news
    """
    import re
    safe = re.sub(r"[^\w\-]", "_", title)
    safe = re.sub(r"_+", "_", safe).strip("_")[:50]
    return os.path.join(base_dir, f"{date.today()}_{safe}")


def run():
    """메인 실행 함수"""
    logger.info("=" * 60)
    logger.info("AI 자동화 뉴스 콘텐츠 생성 시스템 시작")
    logger.info(f"실행 날짜: {date.today()}")
    logger.info("=" * 60)

    # ── 1. 환경변수 로드 ──────────────────────────────────────────────────────
    config = load_env()

    # ── 2. 뉴스 수집 ──────────────────────────────────────────────────────────
    logger.info("[STEP 1] 뉴스 수집 시작")
    articles = fetch_all_news(max_per_keyword=10)

    if not articles:
        logger.error("수집된 뉴스가 없습니다. 네트워크 연결을 확인하세요.")
        sys.exit(1)

    logger.info(f"수집 완료: {len(articles)}개")

    # ── 3. 필터링 ─────────────────────────────────────────────────────────────
    logger.info("[STEP 2] 뉴스 필터링")
    filtered = filter_news(articles)

    if not filtered:
        logger.warning("필터링 후 뉴스가 없습니다. 원본 뉴스를 사용합니다.")
        filtered = articles[:5]

    logger.info(f"필터링 완료: {len(filtered)}개")

    # ── 4. Claude API 호출 ────────────────────────────────────────────────────
    logger.info("[STEP 3] Claude API 콘텐츠 생성")
    news_text = format_for_prompt(filtered, max_articles=5)

    parsed = generate_content(
        news_text=news_text,
        api_key=config["claude_api_key"],
        use_json=True,
    )

    if not parsed.cards:
        logger.error("Claude 응답에서 카드를 파싱하지 못했습니다.")
        logger.debug(f"Raw 응답:\n{parsed.raw_response}")
        sys.exit(1)

    logger.info(f"카드 생성 완료: {len(parsed.cards)}장")
    logger.info(f"  - 핵심: {parsed.summary_core}")
    logger.info(f"  - 기술: {parsed.summary_tech}")
    logger.info(f"  - 영향: {parsed.summary_impact}")

    # ── 5. 카드 이미지 생성 ───────────────────────────────────────────────────
    logger.info("[STEP 4] 카드 이미지 생성")

    first_title = filtered[0]["title"] if filtered else "AI_news"
    output_dir = make_output_subdir(config["output_dir"], first_title)

    try:
        saved_dir, image_paths = render_cards(
            cards=parsed.cards,
            base_output_dir=config["output_dir"],
            title=first_title,
            template_path="templates/card.html",
        )
        logger.info(f"이미지 생성 완료: {len(image_paths)}장")
        logger.info(f"저장 경로: {os.path.abspath(saved_dir)}")
        for path in image_paths:
            logger.info(f"  → {os.path.basename(path)}")
    except Exception as e:
        logger.error(f"이미지 생성 실패: {e}")
        sys.exit(1)

    # ── 6. 사용된 기사 seen 캐시 등록 ────────────────────────────────────────────
    logger.info("[STEP 5] 사용된 기사 seen 캐시 등록")
    used_articles = filtered[:5]
    mark_articles_as_seen(used_articles)
    logger.info(f"  → {len(used_articles)}개 기사 등록 완료 (다음 실행 시 제외)")

    # ── 7. Description 파일 저장 ──────────────────────────────────────────────
    logger.info("[STEP 6] 인스타그램 description 저장")
    desc_path = save_description(
        output_dir=saved_dir,
        description=parsed.insta_description,
        tags=parsed.insta_tags,
        title=first_title,
    )

    # ── 완료 ──────────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("모든 작업 완료")
    logger.info(f"  - 뉴스 수집: {len(filtered)}개 (신규)")
    logger.info(f"  - 카드 생성: {len(image_paths)}장")
    logger.info(f"  - 저장 위치: {os.path.abspath(saved_dir)}")
    logger.info(f"  - description: {os.path.abspath(desc_path)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    run()
