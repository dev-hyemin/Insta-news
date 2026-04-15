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
    title: str = ""                              # 굵은 헤드라인 (20자 이내)
    body: str = ""                               # 상세 내용 (2~3줄, \n 구분)
    category: str = ""                           # 카테고리 태그 (예: "AI | 자동화")
    keywords: list = field(default_factory=list) # 키워드 태그 ["#AI자동화", "#LLM"]
    text: str = ""                               # 레거시 전체 텍스트 (폴백용)


@dataclass
class ParsedContent:
    """Claude 응답 파싱 결과"""
    cards: list[CardContent] = field(default_factory=list)
    summary_core: str = ""
    summary_tech: str = ""
    summary_impact: str = ""
    idea_1: str = ""
    idea_2: str = ""
    insta_description: str = ""   # 인스타 게시물 본문
    insta_tags: list = field(default_factory=list)  # 해시태그 리스트
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

다음 뉴스를 기반으로 인스타그램 카드뉴스 콘텐츠를 생성하고, 반드시 아래 JSON 형식으로만 응답하라.
JSON 외의 다른 텍스트는 절대 포함하지 마라.

{{
  "cards": [
    {{
      "index": 1,
      "category": "AI NEWS",
      "title": "커버 헤드라인 (20자 이내, 강렬하게)",
      "body": "핵심 한 줄 소개",
      "keywords": ["#AI자동화", "#LLM", "#개발자트렌드"]
    }},
    {{
      "index": 2,
      "category": "AI | 자동화",
      "title": "핵심 인사이트 제목 (15자 이내)",
      "body": "첫 번째 줄: 핵심 사실\\n두 번째 줄: 개발자 관점 해석\\n세 번째 줄: 실무 적용 포인트",
      "keywords": ["#키워드1", "#키워드2", "#키워드3"]
    }},
    {{
      "index": 3,
      "category": "LLM | 개발",
      "title": "두 번째 인사이트 제목",
      "body": "내용 2~3줄",
      "keywords": ["#키워드1", "#키워드2", "#키워드3"]
    }},
    {{
      "index": 4,
      "category": "산업 | 트렌드",
      "title": "세 번째 인사이트 제목",
      "body": "내용 2~3줄",
      "keywords": ["#키워드1", "#키워드2", "#키워드3"]
    }},
    {{
      "index": 5,
      "category": "기술 | 실무",
      "title": "자동화 활용 제목",
      "body": "자동화 적용 방법 2~3줄",
      "keywords": ["#키워드1", "#키워드2", "#키워드3"]
    }},
    {{
      "index": 6,
      "category": "정리 | 요약",
      "title": "오늘의 핵심 정리",
      "body": "전체 요약 1~2줄\\n저장하고 팔로우하면 매일 AI 뉴스 받아보기 ✓",
      "keywords": ["#키워드1", "#키워드2", "#키워드3"]
    }}
  ],
  "summary": {{
    "core": "핵심 내용",
    "tech": "관련 기술",
    "impact": "개발자에게 미치는 영향"
  }},
  "ideas": {{
    "idea_1": "자동화 아이디어 1",
    "idea_2": "자동화 아이디어 2"
  }},
  "instagram": {{
    "description": "인스타그램 게시물 본문 (아래 형식 준수):\n첫 줄: 강렬한 훅 문장 (숫자/질문/충격적 사실)\n\n둘째 단락: 오늘 카드에서 다루는 핵심 내용 2~3줄\n\n셋째 단락: 개발자에게 왜 중요한지 1~2줄\n\n마지막 줄: 저장하고 팔로우하면 매일 AI 뉴스를 받을 수 있어요 👉 @findev.ai",
    "tags": ["#AI자동화", "#LLM", "#금융권개발자", "#개발자", "#인공지능", "#findevai", "추가 관련 태그 25~30개"]
  }}
}}

카드 작성 규칙:
- title: 20자 이내, 임팩트 있는 헤드라인, 숫자/비교/질문 활용
- body: \\n으로 줄바꿈, 2~3줄, 쉬운 표현, 개발자 관점 필수
- category: "영역 | 세부" 형식 (예: "AI | 자동화", "LLM | 개발")
- keywords: 해당 카드 핵심 키워드 3~4개, 반드시 # 접두사 포함, 한국어 또는 영어 (예: "#AI자동화", "#LLM", "#금융개발자")
- 1장은 커버(티저), 6장은 아웃트로(CTA), 2~5장은 핵심 인사이트
- instagram.description: 한국어, 개발자 타겟, 이모지 1~2개 활용, 줄바꿈은 \\n 사용
- instagram.tags: # 포함, 25~30개, 한국어+영어 혼합, 뉴스 주제 관련 태그 위주
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
        CardContent(
            index=c["index"],
            title=c.get("title", ""),
            body=c.get("body", ""),
            category=c.get("category", "AI NEWS"),
            keywords=c.get("keywords", []),
            text=c.get("text", c.get("body", "")),  # 레거시 폴백
        )
        for c in data.get("cards", [])
    ]

    summary = data.get("summary", {})
    ideas = data.get("ideas", {})

    instagram = data.get("instagram", {})

    return ParsedContent(
        cards=cards,
        summary_core=summary.get("core", ""),
        summary_tech=summary.get("tech", ""),
        summary_impact=summary.get("impact", ""),
        idea_1=ideas.get("idea_1", ""),
        idea_2=ideas.get("idea_2", ""),
        insta_description=instagram.get("description", ""),
        insta_tags=instagram.get("tags", []),
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
