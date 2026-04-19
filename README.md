# financial-intelligence-hub

`financial-intelligence-hub`는 DART(전자공시시스템) IR 자료를 자동으로 수집·분석하는 CLI입니다.  
7개의 계층형 AgentSkills(`financial-intelligence-hub` → `dart-ir-analyzer-scenario` → 3개 컴포넌트 → 2개 유틸리티)가 포함되어 있습니다.

패키지는 PyPI에 [`financial-intelligence-hub`](https://pypi.org/project/financial-intelligence-hub/) 로 배포됩니다.

---

## 한국어 소개

`financial-intelligence-hub`는 기업 IR 자료를 에이전트 실행 흐름으로 바로 연결하기 위한 CLI입니다.

핵심은 단일 스크립트 실행이 아닙니다.

- 7개의 AgentSkill이 **L1 Root → L2 Scenario → L3 Components → L4 Utilities** 계층으로 오케스트레이션되고
- 각 스킬은 독립적으로 로드·교체·확장 가능하며
- `fih install --skills` 한 줄로 Claude, Codex, Cursor 같은 에이전트 환경에 계층 전체를 설치하는 것

### 포함된 스킬 (7개)

| 레이어 | 스킬명 | 역할 |
|-------|--------|------|
| L1 Root | `financial-intelligence-hub` | 진입점·오케스트레이터·대시보드 렌더링 |
| L2 Scenario | `dart-ir-analyzer-scenario` | 6단계 파이프라인 관장 |
| L3 Component | `corpcode-resolver` | 기업명 → corp_code (Fuzzy Matching) |
| L3 Component | `context-aware-chunker` | 재무 섹션 필터링 + 슬라이딩 윈도우 청킹 |
| L3 Component | `solar-insight-extractor` | Solar LLM 호출 + JSON 파싱 안정화 |
| L4 Utility | `dart-api-connector` | DART API 명세·코드표·Gotchas |
| L4 Utility | `output-schema-validator` | 출력 JSON 스펙 검증 + 보정 지침 |

### 왜 계층형 스킬인가

단일 스킬은 컨텍스트 윈도우를 과도하게 소비한다.

- AgentSkills의 Progressive Disclosure 원칙에 따라 에이전트는 필요한 스킬만 로드한다
- L4 유틸리티는 명세만 담고 실행하지 않아 재사용성이 높다
- L3 컴포넌트는 독립적으로 교체 가능해 Solar LLM 대신 다른 LLM으로 전환 시 `solar-insight-extractor`만 수정하면 된다

### 현재 상태

- `dart-ir-analyzer-scenario`: 코스피200 기준 실사용 가능
- `data_confidence=high` 비율: 주요 대형주 기준 ~75%
- 소형주·비정기 공시: challenge 영역으로 별도 추적 중

### 설치

전역 설치:

```
pip install financial-intelligence-hub
```

로컬 개발 설치:

```
pip install -e ".[dev]"
```

### 인증

API 키 우선순위:

1. `DART_API_KEY`, `UPSTAGE_API_KEY` 환경변수
2. `~/.config/fih/config.json`

```
fih configure
```

### 빠른 시작

IR 자료 분석:

```
fih analyze 삼성전자
fih analyze 삼성전자 --format json --save result.json
```

복수 기업 비교:

```
fih compare 삼성전자 SK하이닉스
```

스킬 설치:

```
fih install --skills
```

Claude / Codex / Cursor용으로 함께 설치:

```
fih install --skills --all-targets
```

---

## English Overview

`financial-intelligence-hub` is a Korean financial disclosure (DART) IR analysis CLI built on Upstage APIs.  
It ships with 7 hierarchical Agent Skills organized across 4 layers.

The tool turns DART disclosure PDFs into:

- structured financial KPIs (revenue, operating income, YoY change)
- segment performance summaries
- forward guidance and risk factors
- dashboard-formatted output in the terminal

### Bundled skills (7)

```
financial-intelligence-hub (L1)
└── dart-ir-analyzer-scenario (L2)
    ├── corpcode-resolver (L3)
    ├── context-aware-chunker (L3)
    ├── solar-insight-extractor (L3)
    ├── dart-api-connector (L4)
    └── output-schema-validator (L4)
```

### Why layered skills

A monolithic skill over-consumes context. The layered structure follows AgentSkills' Progressive Disclosure principle — agents load only what they need per task. L4 utilities are pure specs (no execution), making them reusable across scenarios. L3 components are independently swappable.

---

## Install

Global install:

```
pip install financial-intelligence-hub
```

Development:

```
pip install -e ".[dev]"
```

CLI binary:

```
fih
```

---

## Authentication

The CLI resolves API keys in this order:

1. `DART_API_KEY`, `UPSTAGE_API_KEY` environment variables
2. `~/.config/fih/config.json`

Run `fih configure` to save keys locally.

---

## Commands

### Analyze IR

```
fih analyze 삼성전자
fih analyze 삼성전자 --format json --save result.json
fih analyze 삼성전자 --format markdown --verbose
fih analyze 삼성전자 --cache-only
```

Useful options:

- `--format table | json | markdown`
- `--save <path.json>`
- `--verbose` — show per-step pipeline logs
- `--cache-only` — use cached parse/LLM results only

### Compare companies

```
fih compare 삼성전자 SK하이닉스
fih compare 삼성전자 SK하이닉스 NAVER --format json
```

### Run API server

```
fih serve
fih serve --port 8080 --reload
```

POST `/analyze`:

```
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"company_name": "삼성전자"}'
```

GET `/skills` — 설치된 스킬 목록:

```
curl http://localhost:8000/skills
```

### Install bundled skills

Install all 7 skills into the current project:

```
fih install --skills
```

Preview without installing:

```
fih install --skills --dry-run
```

Install specific layer only:

```
fih install --skills --layer L3
```

Install into multiple agent targets:

```
fih install --skills --all-targets
```

Or explicitly:

```
fih install --skills --targets claude,codex,cursor
```

Installed paths:

```
~/.claude/skills/financial-intelligence-hub/
~/.claude/skills/dart-ir-analyzer-scenario/
~/.claude/skills/corpcode-resolver/
~/.claude/skills/context-aware-chunker/
~/.claude/skills/solar-insight-extractor/
~/.claude/skills/dart-api-connector/
~/.claude/skills/output-schema-validator/
```

### Check installed skills

```
fih list-skills
fih list-skills --agent codex
```

### Run regression batches

```
fih regression-batch \
  --manifest fixtures/regression/public-hardening-v1.json \
  --out-dir tmp/regression-public-hardening-ci
```

With assert gate and resume:

```
fih regression-batch \
  --manifest fixtures/regression/public-hardening-v1.json \
  --out-dir tmp/regression-public-hardening-ci \
  --assert \
  --resume \
  --cache-only
```

### Clear cache

```
fih cache-clear all --dry-run
fih cache-clear parse
fih cache-clear llm
fih cache-clear corp
```

---

## Pipeline

### `analyze` / `compare`

1. `corpcode-resolver` (L3) — 기업명 퍼지 매칭 → `corp_code`
2. `dart-api-connector` (L4) 명세 참조 — 공시 목록 API → `rcept_no`
3. DART 뷰어 HTML 스크래핑 3단계 폴백 → PDF URL
4. Upstage Document Parse → 레이아웃 보존 Markdown
5. `context-aware-chunker` (L3) — 재무 섹션 필터링 + 슬라이딩 윈도우 청킹
6. `solar-insight-extractor` (L3) — Solar LLM → JSON
7. `output-schema-validator` (L4) — 검증 + 보정 → 표준 응답

---

## Technical highlights

- Python 3.10+
- `typer` + `rich` 기반 CLI
- `fastapi` + `uvicorn` API 서버
- 7개 계층형 AgentSkills (L1~L4) — AgentSkills 표준 호환
- `fih install --skills` 한 줄 설치, `--layer` 레이어 선택 설치
- `fih list-skills` 설치 상태 확인
- DART `CORPCODE.xml` ZIP 파싱 + 퍼지 기업명 매칭
- PDF 추출 3단계 폴백 + 레이아웃 보존 파싱
- 재무 키워드 섹션 필터링 + 슬라이딩 윈도우 청킹
- `temperature: 0.0` + JSON 펜스 제거로 LLM 출력 안정화
- 로컬 파일 캐시 (corp / parse / llm scope 분리, `.fih-cache/`)
- 회귀 배치 + `--assert` 릴리스 게이트

---

## Validation

```
pytest tests/
```

배치 회귀 검증:

```
fih regression-batch \
  --manifest fixtures/regression/public-hardening-v1.json \
  --out-dir tmp/regression-ci \
  --assert \
  --cache-only
```

---

## Package contents

이 패키지에는 아래가 포함됩니다:

- CLI 런타임 (`src/`)
- 7개 AgentSkill (`skills/`)
- 스킬 레지스트리 (`config/skills-registry.json`)
- 회귀 테스트 픽스처 (`fixtures/regression/`)

하나의 Python 패키지가 7개 AgentSkill과 CLI를 함께 배포합니다.
