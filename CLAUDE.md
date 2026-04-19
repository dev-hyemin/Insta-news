# Insta-news — Claude Code 인수인계

## 프로젝트 개요
AI/개발자 뉴스를 자동 수집하고 Claude API로 인스타그램 뉴스카드 콘텐츠를 생성하는 Python 자동화 시스템.

## 현재 브랜치
`claude/ai-news-automation-WZfeR` → `main` squash merge 완료  
이후 작업은 새 브랜치를 만들어 진행할 것.

---

## 완료된 작업

### 구현된 파일 구조
```
Insta-news/
 ├─ main.py                  # 파이프라인 오케스트레이션
 ├─ services/
 │   ├─ news.py              # RSS 수집 + 파일 기반 중복 제거
 │   ├─ claude.py            # Claude API 호출 + JSON/텍스트 파싱
 │   └─ render.py            # HTML 템플릿 → 1080×1350 PNG 렌더링
 ├─ templates/
 │   └─ card.html            # 다크 테마 카드 (cover/content/outro 3종)
 ├─ .env.example
 └─ requirements.txt
```

### 주요 설계 결정
- **feedparser 제거**: Python 3.11에서 sgmllib 제거로 빌드 실패 → `xml.etree.ElementTree`로 직접 RSS 파싱
- **Redis 제거**: `data/seen_articles.json`으로 파일 기반 중복 제거 (30일 TTL)
- **Notion 제거**: 불필요한 외부 의존성 제거
- **Chrome 자동 탐지**: `CHROME_PATH` 환경변수 → Playwright Chromium → 시스템 Chrome 순 탐색
- **이미지 크기**: 1080×1350 (인스타그램 4:5 비율)
- **카드 타입**: 1장=cover, 2~5장=content, 6장=outro

### 실행 흐름 (main.py)
1. Google News RSS 수집 (키워드: AI automation, LLM, developer)
2. 키워드 필터링 (AI, automation, LLM, developer, API)
3. Claude API → JSON 응답 파싱 (title, body, category, keywords 구조)
4. html2image로 카드 PNG 생성 → `OUTPUT_DIR/{date}_{title}/card_1~6.png`
5. 사용된 기사 `data/seen_articles.json` 캐시 등록
6. 인스타그램 게시물 본문 `description.txt` 저장

---

## 다음 작업: Figma 연동

### 목표
하이브리드 방식으로 Figma 연동:
- **템플릿 수정 요청 시**: Python → Figma API (Write) → Figma 프레임 노드 수정
- **이미지 생성 시**: Figma API (Read/Export) → 템플릿 PNG export → Pillow로 텍스트 합성 → 로컬 PNG 저장

### 필요한 신규 파일
- `services/figma.py` 신규 생성
  - `export_template(node_id)` — 프레임 PNG export
  - `update_template(node_id, properties)` — 노드 텍스트/스타일 수정
- `services/render.py` 수정
  - html2image 방식과 Figma 방식 병행 지원 (환경변수로 분기)

### 환경변수 (.env에 추가 필요)
```env
FIGMA_API_TOKEN=figd_xxxx          # File content Read+Write, Exports Read
FIGMA_FILE_ID=AbCdEfGhIjKl
FIGMA_NODE_ID=123:456              # 단일 템플릿 프레임
# 카드별 프레임이 따로 있다면:
# FIGMA_NODE_IDS=123:456,123:457,123:458,123:459,123:460,123:461
```

### Figma API 권한
| 스코프 | 권한 |
|--------|------|
| File content | Read + Write |
| File metadata | Read only |
| Exports | Read only |

### Figma API 엔드포인트 (참고)
- `GET /v1/files/{file_key}/nodes?ids={node_id}` — 노드 구조 조회
- `GET /v1/images/{file_key}?ids={node_id}&format=png&scale=2` — PNG export
- `PUT /v1/files/{file_key}/nodes/{node_id}` — 노드 속성 수정

---

## 환경 정보
- Python 3.11
- 의존성: `requirements.txt` 참고 (`anthropic>=0.95.0` 사용)
- Playwright Chromium: `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` (이 환경 한정)
- Google News RSS: 서버 IP 차단 있음 → 로컬 실행 시 정상 동작
