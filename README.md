# Insta-news

AI/개발자 뉴스를 자동 수집하고 Claude API로 인스타그램 뉴스카드 콘텐츠를 생성하는 Python 자동화 시스템.

## 기능

- **뉴스 수집**: Google News RSS로 AI/LLM/개발 관련 최신 뉴스 수집
- **콘텐츠 생성**: Claude API로 인스타 카드 6장 + 개발자 요약 + 자동화 아이디어 생성
- **카드 이미지**: HTML 다크 테마 템플릿 기반 1080×1080 PNG 이미지 생성
  - `OUTPUT_DIR/{date}_{title}/card_1.png ~ card_6.png` 구조로 저장

## 파일 구조

```
Insta-news/
 ├─ main.py               # 메인 실행 파일
 ├─ services/
 │   ├─ news.py           # 뉴스 수집 및 필터링
 │   ├─ claude.py         # Claude API 호출 및 파싱
 │   └─ render.py         # HTML → PNG 카드 이미지 렌더링
 ├─ templates/
 │   └─ card.html         # 다크 테마 카드 HTML 템플릿
 ├─ .env                  # 환경변수 (직접 생성 필요)
 ├─ .env.example          # 환경변수 예시
 └─ requirements.txt      # 의존성 목록
```

## 설치

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일을 열어 API 키 입력
```

## 환경변수 설정

`.env` 파일에 아래 값을 입력:

```env
CLAUDE_API_KEY=your_claude_api_key_here

# 이미지 저장 기본 경로 (절대/상대 경로 모두 가능, 기본값: ./output)
OUTPUT_DIR=output

# 선택: Redis 중복 제거
REDIS_URL=redis://localhost:6379/0
```

## 실행

```bash
python main.py
```

### 실행 결과

`OUTPUT_DIR` 하위에 `{날짜}_{뉴스제목}/` 디렉토리가 생성되고 카드 이미지가 저장됩니다.

```
output/
 └─ 2026-04-15_AI_automation_latest_news/
     ├─ card_1.png
     ├─ card_2.png
     ├─ card_3.png
     ├─ card_4.png
     ├─ card_5.png
     └─ card_6.png
```

절대 경로 지정 예시:

```env
OUTPUT_DIR=/Users/me/Desktop/insta-cards
```

```
/Users/me/Desktop/insta-cards/
 └─ 2026-04-15_AI_automation_latest_news/
     ├─ card_1.png
     ...
```

## 기술 스택

- Python 3.11
- [anthropic](https://pypi.org/project/anthropic/) — Claude API SDK
- [feedparser](https://pypi.org/project/feedparser/) — RSS 파싱
- [requests](https://pypi.org/project/requests/) — HTTP 클라이언트
- [html2image](https://pypi.org/project/html2image/) — HTML → PNG 변환
- [python-dotenv](https://pypi.org/project/python-dotenv/) — 환경변수 관리
- [redis](https://pypi.org/project/redis/) — 중복 뉴스 제거 (선택, `REDIS_URL` 설정 시 활성화)

## 추가 개선 옵션

- **cron 스케줄링**: `crontab -e`로 매일 자동 실행
  ```
  0 9 * * * cd /path/to/Insta-news && python main.py
  ```
- **Redis 중복 제거**: `.env`에 `REDIS_URL` 설정 시 7일간 중복 뉴스 자동 필터링
- **JSON 응답 모드**: `generate_content(..., use_json=True)` (기본값) — Claude 응답을 구조화된 JSON으로 파싱
