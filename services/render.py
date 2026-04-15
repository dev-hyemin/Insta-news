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
OUTPUT_DIR = "output"


def render_cards(
    cards: list[CardContent],
    template_path: str = "templates/card.html",
    output_dir: str = OUTPUT_DIR,
    title_prefix: str = "news",
) -> list[str]:
    """
    카드 리스트를 PNG 이미지로 렌더링

    Args:
        cards: CardContent 리스트
        template_path: HTML 템플릿 파일 경로
        output_dir: 이미지 출력 디렉토리
        title_prefix: 파일명 접두사 (안전 처리 후 사용)

    Returns:
        생성된 이미지 파일 경로 리스트
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    template_html = _load_template(template_path)
    safe_prefix = _safe_filename(title_prefix)

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
        filename = f"{safe_prefix}_card_{card.index}.png"
        output_path = os.path.join(output_dir, filename)

        try:
            hti.screenshot(
                html_str=html,
                save_as=filename,
            )
            logger.info(f"카드 이미지 생성: {output_path}")
            generated_paths.append(output_path)
        except Exception as e:
            logger.error(f"카드 {card.index} 이미지 생성 실패: {e}")

    return generated_paths


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
