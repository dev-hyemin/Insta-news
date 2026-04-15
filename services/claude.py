"""
Claude API 호출 및 응답 파싱 모듈
anthropic SDK를 사용하여 뉴스 콘텐츠를 생성하고 구조화된 데이터로 파싱한다.
"""

import json
import logging
import re
from dataclasses import dataclass, field

import anthropic

logger = logging.getLogger(__name__)

# 사용 모델
MODEL = "claude-sonnet-4-6"

# 최대 토큰
MAX_TOKENS = 4096


@dataclass
class CardContent:
    """인스타 뉴스카드 단일 장"""
    index: int
    text: str


@dataclass
class ParsedContent:
    """Claude 응답 파싱 결과"""
    cards: list[CardContent] = field(default_factory=list)
    summary_core: str = ""
    summary_tech: str = ""
    summary_impact: str = ""
    idea_1: str = ""
    idea_2: str = ""
    raw_response: str = ""


def build_prompt(news_text: str) -> str:
    """Claude 프롬프트 빌드"""
    return f"""너는 개발자를 위한 AI 자동화 전문가다.

다음 내용을 기반으로 3가지 결과를 만들어라.

1. 인스타 뉴스카드 (6장)
2. 개발자용 요약
3. 자동화 아이디어

조건:
- 각 카드 2~3줄
- 쉬운 표현 사용
- 반드시 자동화 방법 포함
- 개발자 관점 추가

출력 형식:

[뉴스카드]
1장:
2장:
3장:
4장:
5장:
6장:

[개발자 요약]
- 핵심:
- 기술:
- 영향:

[자동화 아이디어]
- 아이디어1:
- 아이디어2:

---

입력 데이터:
{news_text}"""


def build_json_prompt(news_text: str) -> str:
    """JSON 형식 응답을 요청하는 프롬프트"""
    return f"""너는 개발자를 위한 AI 자동화 전문가다.

다음 뉴스를 기반으로 콘텐츠를 생성하고, 반드시 아래 JSON 형식으로만 응답하라.
JSON 외의 다른 텍스트는 절대 포함하지 마라.

{{
  "cards": [
    {{"index": 1, "text": "카드 내용 2~3줄"}},
    {{"index": 2, "text": "카드 내용 2~3줄"}},
    {{"index": 3, "text": "카드 내용 2~3줄"}},
    {{"index": 4, "text": "카드 내용 2~3줄"}},
    {{"index": 5, "text": "카드 내용 2~3줄"}},
    {{"index": 6, "text": "카드 내용 2~3줄"}}
  ],
  "summary": {{
    "core": "핵심 내용",
    "tech": "관련 기술",
    "impact": "개발자에게 미치는 영향"
  }},
  "ideas": {{
    "idea_1": "자동화 아이디어 1",
    "idea_2": "자동화 아이디어 2"
  }}
}}

조건:
- 각 카드는 2~3줄, 쉬운 표현, 자동화 방법 포함, 개발자 관점
- summary와 ideas는 한국어로 작성

입력 데이터:
{news_text}"""


def generate_content(news_text: str, api_key: str, use_json: bool = True) -> ParsedContent:
    """
    Claude API 호출 및 콘텐츠 생성

    Args:
        news_text: 프롬프트에 삽입할 뉴스 텍스트
        api_key: Claude API 키
        use_json: True면 JSON 프롬프트 사용, False면 텍스트 파싱

    Returns:
        ParsedContent 객체
    """
    client = anthropic.Anthropic(api_key=api_key)

    if use_json:
        prompt = build_json_prompt(news_text)
    else:
        prompt = build_prompt(news_text)

    logger.info(f"Claude API 호출 중 (model={MODEL}, json_mode={use_json})")

    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
        logger.info("Claude API 응답 수신 완료")
        logger.debug(f"Raw response (앞 200자): {raw[:200]}")

    except anthropic.AuthenticationError:
        logger.error("Claude API 인증 실패: API 키를 확인하세요")
        raise
    except anthropic.RateLimitError:
        logger.error("Claude API rate limit 초과")
        raise
    except anthropic.APIError as e:
        logger.error(f"Claude API 오류: {e}")
        raise

    # JSON 모드 파싱 시도, 실패 시 텍스트 파싱으로 폴백
    if use_json:
        parsed = _parse_json_response(raw)
        if parsed:
            return parsed
        logger.warning("JSON 파싱 실패, 텍스트 파싱으로 폴백")

    return _parse_text_response(raw)


def _parse_json_response(raw: str) -> ParsedContent | None:
    """JSON 응답 파싱"""
    # 마크다운 코드 블록 제거
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()

    # JSON 객체 추출
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as e:
        logger.warning(f"JSON 디코딩 실패: {e}")
        return None

    cards = [
        CardContent(index=c["index"], text=c["text"])
        for c in data.get("cards", [])
    ]

    summary = data.get("summary", {})
    ideas = data.get("ideas", {})

    return ParsedContent(
        cards=cards,
        summary_core=summary.get("core", ""),
        summary_tech=summary.get("tech", ""),
        summary_impact=summary.get("impact", ""),
        idea_1=ideas.get("idea_1", ""),
        idea_2=ideas.get("idea_2", ""),
        raw_response=raw,
    )


def _parse_text_response(raw: str) -> ParsedContent:
    """텍스트 형식 응답 파싱"""
    result = ParsedContent(raw_response=raw)

    # 뉴스카드 섹션 파싱
    card_section = _extract_section(raw, "[뉴스카드]", ["[개발자 요약]", "[자동화 아이디어]"])
    if card_section:
        result.cards = _parse_cards(card_section)

    # 개발자 요약 섹션 파싱
    summary_section = _extract_section(raw, "[개발자 요약]", ["[자동화 아이디어]"])
    if summary_section:
        result.summary_core = _extract_field(summary_section, "핵심")
        result.summary_tech = _extract_field(summary_section, "기술")
        result.summary_impact = _extract_field(summary_section, "영향")

    # 자동화 아이디어 섹션 파싱
    idea_section = _extract_section(raw, "[자동화 아이디어]", [])
    if idea_section:
        result.idea_1 = _extract_field(idea_section, "아이디어1")
        result.idea_2 = _extract_field(idea_section, "아이디어2")

    return result


def _extract_section(text: str, start_marker: str, end_markers: list[str]) -> str:
    """마커 사이의 섹션 텍스트 추출"""
    start_idx = text.find(start_marker)
    if start_idx == -1:
        return ""

    start_idx += len(start_marker)
    end_idx = len(text)

    for end_marker in end_markers:
        idx = text.find(end_marker, start_idx)
        if idx != -1 and idx < end_idx:
            end_idx = idx

    return text[start_idx:end_idx].strip()


def _parse_cards(card_section: str) -> list[CardContent]:
    """카드 섹션에서 6장 카드 파싱"""
    cards = []
    pattern = re.compile(r"(\d+)장:\s*(.*?)(?=\d+장:|$)", re.DOTALL)

    for match in pattern.finditer(card_section):
        index = int(match.group(1))
        text = match.group(2).strip()
        if text:
            cards.append(CardContent(index=index, text=text))

    return cards


def _extract_field(section: str, field_name: str) -> str:
    """섹션에서 특정 필드 값 추출"""
    pattern = re.compile(rf"-\s*{re.escape(field_name)}:\s*(.+?)(?=\n-|\Z)", re.DOTALL)
    match = pattern.search(section)
    if match:
        return match.group(1).strip()
    return ""
