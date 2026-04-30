"""
카드 이미지 렌더링 모듈
HTML 템플릿을 기반으로 1080x1080 인스타그램 뉴스카드 이미지를 생성한다.
"""

import logging
import os
import re
from datetime import date
from pathlib import Path

from html2image import Html2Image

from services.claude import CardContent

logger = logging.getLogger(__name__)

CARD_WIDTH  = 1080
CARD_HEIGHT = 1350  # 4:5 비율 (인스타그램 피드 최적)

# Playwright 번들 Chromium 경로 (시스템 Chrome 없는 환경 대응)
_PLAYWRIGHT_CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def _find_chrome() -> str | None:
    """사용 가능한 Chrome/Chromium 실행 파일 경로 반환"""
    # 1. 환경변수 우선
    env_path = os.getenv("CHROME_PATH", "")
    if env_path and Path(env_path).exists():
        return env_path

    # 2. Playwright 번들 Chromium
    if Path(_PLAYWRIGHT_CHROME).exists():
        return _PLAYWRIGHT_CHROME

    # 3. 시스템 경로 (None → html2image 기본 탐색)
    return None


def render_cards(
    cards: list[CardContent],
    output_dir: str,
    template_path: str = "templates/card.html",
) -> tuple[str, list[str]]:
    """
    카드 리스트를 PNG 이미지로 렌더링

    Args:
        cards: CardContent 리스트
        output_dir: 이미지를 저장할 디렉토리 경로 (호출자가 날짜 포함 경로 전달)
        template_path: HTML 템플릿 파일 경로

    Returns:
        (저장 디렉토리 경로, 생성된 이미지 파일 경로 리스트)
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    logger.info(f"출력 디렉토리: {os.path.abspath(output_dir)}")

    template_html = _load_template(template_path)
    chrome_path = _find_chrome()

    hti_kwargs: dict = dict(
        size=(CARD_WIDTH, CARD_HEIGHT),
        output_path=output_dir,
        custom_flags=["--no-sandbox", "--disable-gpu", "--hide-scrollbars"],
    )
    if chrome_path:
        hti_kwargs["browser_executable"] = chrome_path
        logger.info(f"Chrome 경로: {chrome_path}")

    hti = Html2Image(**hti_kwargs)

    generated_paths: list[str] = []

    total = len(cards)
    for card in cards:
        html = _inject_content(template_html, card, total=total)
        filename = f"card_{card.index}.png"
        output_path = os.path.join(output_dir, filename)

        try:
            hti.screenshot(html_str=html, save_as=filename)
            logger.info(f"  card_{card.index}.png 생성 완료")
            generated_paths.append(output_path)
        except Exception as e:
            logger.error(f"카드 {card.index} 이미지 생성 실패: {e}")

    return output_dir, generated_paths


def _load_template(template_path: str) -> str:
    """HTML 템플릿 파일 로드"""
    path = Path(template_path)
    if not path.exists():
        raise FileNotFoundError(f"HTML 템플릿 파일을 찾을 수 없습니다: {template_path}")
    return path.read_text(encoding="utf-8")


def _inject_content(template: str, card: CardContent, total: int = 6) -> str:
    """HTML 템플릿에 카드 콘텐츠 주입"""
    # 카드 타입 결정
    if card.index == 1:
        card_type = "cover"
    elif card.index == total:
        card_type = "outro"
    else:
        card_type = "content"

    # 진행 도트 생성
    dots_html = ""
    for i in range(1, total + 1):
        cls = "dot on" if i == card.index else "dot"
        dots_html += f'<div class="{cls}"></div>'

    # 타이틀 / 본문 결정 (title/body 없으면 레거시 text 폴백)
    title_src = card.title or card.text or ""
    body_src  = card.body  or ""

    # 커버 카드: body에 중복 스와이프 문구가 있으면 제거 (템플릿이 date-badge로 처리)
    if card_type == "cover":
        body_src = re.sub(r"\n?→\s*스와이프.+", "", body_src).strip()
        body_src = re.sub(r"\n?스와이프.+확인.*", "", body_src).strip()

    title_html = title_src.replace("\n", "<br>")
    body_html  = body_src.replace("\n", "<br>")
    category   = card.category or "AI NEWS"
    seq_label  = f"{card.index:02d} / {total:02d}"
    date_label = date.today().strftime("%Y.%m.%d") + "  ·  오늘의 AI 뉴스"

    # 키워드 태그 HTML 생성
    keywords_html = ""
    for kw in (card.keywords or []):
        kw = kw.strip()
        if kw:
            keywords_html += f'<span class="kw-tag">{kw}</span>'

    result = template
    result = result.replace("{{CARD_TYPE}}",     card_type)
    result = result.replace("{{CARD_INDEX}}",    str(card.index))
    result = result.replace("{{CARD_SEQ}}",      seq_label)
    result = result.replace("{{CARD_CATEGORY}}", category)
    result = result.replace("{{CARD_TITLE}}",    title_html)
    result = result.replace("{{CARD_BODY}}",     body_html)
    result = result.replace("{{CARD_KEYWORDS}}", keywords_html)
    result = result.replace("{{CARD_DATE}}",     date_label)
    result = result.replace("{{PROGRESS_DOTS}}", dots_html)
    return result


def save_description(
    output_dir: str,
    description: str,
    tags: list[str],
    title: str = "",
) -> str:
    """
    인스타그램 업로드용 description.txt 저장

    Args:
        output_dir: 카드 이미지가 저장된 디렉토리
        description: 게시물 본문
        tags: 해시태그 리스트
        title: 뉴스 제목 (파일 상단 메타 정보용)

    Returns:
        저장된 파일 경로
    """
    today = date.today().strftime("%Y.%m.%d")
    tags_str = "  ".join(tags)  # 태그 사이 2칸 공백 (인스타 표준)

    content = f"""금융권개발자  ·  {today}

{description}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{tags_str}
"""

    file_path = os.path.join(output_dir, "description.txt")
    Path(file_path).write_text(content.strip(), encoding="utf-8")
    logger.info(f"description.txt 저장 완료: {file_path}")
    return file_path
