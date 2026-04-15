"""
카드 이미지 렌더링 모듈
HTML 템플릿을 기반으로 1080x1080 인스타그램 뉴스카드 이미지를 생성한다.
"""

import logging
import os
import re
from pathlib import Path

from html2image import Html2Image

from services.claude import CardContent

logger = logging.getLogger(__name__)

CARD_WIDTH = 1080
CARD_HEIGHT = 1080


def render_cards(
    cards: list[CardContent],
    template_path: str = "templates/card.html",
    base_output_dir: str = "output",
    title: str = "news",
) -> tuple[str, list[str]]:
    """
    카드 리스트를 PNG 이미지로 렌더링

    base_output_dir 하위에 title 기반 서브디렉토리를 생성하고
    그 안에 card_1.png ~ card_N.png 를 저장한다.

    Args:
        cards: CardContent 리스트
        template_path: HTML 템플릿 파일 경로
        base_output_dir: 베이스 출력 디렉토리 (절대/상대 경로 모두 가능)
        title: 서브디렉토리 이름의 기반이 될 제목

    Returns:
        (서브디렉토리 경로, 생성된 이미지 파일 경로 리스트)
    """
    safe_title = _safe_filename(title)
    output_dir = os.path.join(base_output_dir, safe_title)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    logger.info(f"출력 디렉토리: {os.path.abspath(output_dir)}")

    template_html = _load_template(template_path)

    hti = Html2Image(
        size=(CARD_WIDTH, CARD_HEIGHT),
        output_path=output_dir,
        custom_flags=[
            "--no-sandbox",
            "--disable-gpu",
            "--hide-scrollbars",
        ],
    )

    generated_paths: list[str] = []

    for card in cards:
        html = _inject_content(template_html, card)
        filename = f"card_{card.index}.png"
        output_path = os.path.join(output_dir, filename)

        try:
            hti.screenshot(
                html_str=html,
                save_as=filename,
            )
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


def _inject_content(template: str, card: CardContent) -> str:
    """HTML 템플릿에 카드 콘텐츠 주입"""
    # 줄바꿈을 <br> 태그로 변환
    text_html = card.text.replace("\n", "<br>")

    result = template.replace("{{CARD_INDEX}}", str(card.index))
    result = result.replace("{{CARD_TEXT}}", text_html)
    return result


def _safe_filename(name: str) -> str:
    """파일명에서 특수문자 제거 및 공백을 언더스코어로 치환"""
    # 알파벳, 숫자, 하이픈, 언더스코어만 허용
    safe = re.sub(r"[^\w\-]", "_", name)
    # 연속 언더스코어 정리
    safe = re.sub(r"_+", "_", safe).strip("_")
    return safe[:50] or "card"
