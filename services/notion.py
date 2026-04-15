"""
Notion API 저장 모듈
뉴스 카드 콘텐츠를 Notion 데이터베이스에 페이지로 저장한다.
"""

import logging
from datetime import date
from typing import Any

import requests

logger = logging.getLogger(__name__)

NOTION_API_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"


class NotionClient:
    """Notion API 클라이언트"""

    def __init__(self, api_key: str, database_id: str):
        self.database_id = database_id
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_API_VERSION,
        }

    def create_page(
        self,
        title: str,
        summary: str,
        body: str,
        tags: list[str] | None = None,
    ) -> dict:
        """
        Notion 데이터베이스에 페이지 생성

        Args:
            title: 페이지 제목 (Name 필드)
            summary: 요약 텍스트 (Summary 필드)
            body: 본문 내용 (Notion 블록으로 변환)
            tags: 태그 목록 (Tag 필드)

        Returns:
            생성된 페이지 응답 dict
        """
        if tags is None:
            tags = ["AI", "Automation"]

        today = date.today().isoformat()

        payload = {
            "parent": {"database_id": self.database_id},
            "properties": self._build_properties(title, summary, today, tags),
            "children": self._build_blocks(body),
        }

        url = f"{NOTION_BASE_URL}/pages"
        logger.info(f"Notion 페이지 생성 중: title='{title}'")

        try:
            resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
            resp.raise_for_status()
            page = resp.json()
            page_id = page.get("id", "")
            logger.info(f"Notion 페이지 생성 완료: id={page_id}")
            return page
        except requests.HTTPError as e:
            logger.error(f"Notion API HTTP 오류: {e.response.status_code} {e.response.text}")
            raise
        except requests.RequestException as e:
            logger.error(f"Notion API 요청 실패: {e}")
            raise

    def _build_properties(
        self,
        title: str,
        summary: str,
        today: str,
        tags: list[str],
    ) -> dict:
        """Notion 페이지 속성(properties) 구성"""
        return {
            "Name": {
                "title": [{"text": {"content": title}}]
            },
            "Summary": {
                "rich_text": [{"text": {"content": summary[:2000]}}]
            },
            "Date": {
                "date": {"start": today}
            },
            "Tag": {
                "multi_select": [{"name": tag} for tag in tags]
            },
        }

    def _build_blocks(self, body: str) -> list[dict]:
        """
        본문 텍스트를 Notion 블록 리스트로 변환

        Notion API는 단일 블록 텍스트 최대 2000자 제한이 있으므로
        줄 단위로 분리하여 paragraph 블록으로 생성한다.
        """
        blocks = []
        lines = body.split("\n")

        for line in lines:
            line = line.rstrip()

            if line.startswith("## "):
                # heading_2 블록
                blocks.append(_heading_block(2, line[3:]))
            elif line.startswith("### "):
                # heading_3 블록
                blocks.append(_heading_block(3, line[4:]))
            elif line.startswith("- **"):
                # 굵은 텍스트 포함 bulleted 리스트
                blocks.append(_rich_bullet_block(line[2:]))
            elif line.startswith("- "):
                blocks.append(_bullet_block(line[2:]))
            elif line == "":
                # 빈 줄 → 빈 paragraph
                blocks.append(_paragraph_block(""))
            else:
                blocks.append(_paragraph_block(line))

            # Notion API: children 배열 최대 100개 제한
            if len(blocks) >= 95:
                break

        return blocks

    def check_database_schema(self) -> dict:
        """데이터베이스 스키마 조회 (디버깅용)"""
        url = f"{NOTION_BASE_URL}/databases/{self.database_id}"
        resp = requests.get(url, headers=self.headers, timeout=10)
        resp.raise_for_status()
        return resp.json()


# ── 블록 헬퍼 함수 ────────────────────────────────────────────────────────────

def _paragraph_block(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text[:2000]}}]
        },
    }


def _heading_block(level: int, text: str) -> dict:
    heading_type = f"heading_{level}"
    return {
        "object": "block",
        "type": heading_type,
        heading_type: {
            "rich_text": [{"type": "text", "text": {"content": text[:2000]}}]
        },
    }


def _bullet_block(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": text[:2000]}}]
        },
    }


def _rich_bullet_block(text: str) -> dict:
    """**bold** 문법을 Notion rich_text annotations으로 변환"""
    rich_text = _parse_bold_text(text)
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": rich_text},
    }


def _parse_bold_text(text: str) -> list[dict]:
    """**text** 패턴을 Notion bold annotations으로 변환"""
    import re
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    rich_text = []
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            rich_text.append({
                "type": "text",
                "text": {"content": part[2:-2][:2000]},
                "annotations": {"bold": True},
            })
        elif part:
            rich_text.append({
                "type": "text",
                "text": {"content": part[:2000]},
            })
    return rich_text or [{"type": "text", "text": {"content": ""}}]
