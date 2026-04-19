---
name: financial-intelligence-hub
description: |
  기업명(또는 ticker)을 입력받아 DART IR 분석부터 결과 대시보드 렌더링까지 전 과정을
  오케스트레이션하는 루트 스킬. dart-ir-analyzer-scenario(L2)를 실행하고 결과를
  구조화된 대시보드로 렌더링한다. 복수 기업 비교, 분기 트렌드, 부문별 성과 시각화를 지원한다.
  "재무 분석", "IR 대시보드", "기업 실적 조회", "Financial Intelligence", "FIH",
  "실적 비교", "분기 실적 보고" 등이 언급될 때 반드시 이 스킬을 활성화할 것.
  단일 기업 분석부터 복수 기업 비교까지 모든 IR 분석 요청의 진입점이다.
compatibility: Python 3.10+, DART_API_KEY, UPSTAGE_API_KEY, 인터넷 접근 필수
metadata:
  layer: "L1-root"
  version: "1.0"
allowed-tools: [Bash]
---

# Financial Intelligence Hub

모든 IR 분석 요청의 진입점이자 오케스트레이터.
하위 스킬을 조합해 사용자에게 대시보드 형태의 결과를 제공한다.

## 스킬 계층 구조

```
financial-intelligence-hub (L1 Root)          ← 이 스킬
└── dart-ir-analyzer-scenario (L2 Scenario)
    ├── corpcode-resolver (L3)
    ├── context-aware-chunker (L3)
    ├── solar-insight-extractor (L3)
    ├── dart-api-connector (L4)
    └── output-schema-validator (L4)
```

---

## 실행 워크플로우

```
- [ ] 1) 사용자 요청 파싱 (기업명, 분기, 비교 모드 여부)
- [ ] 2) dart-ir-analyzer-scenario 실행 (기업당 1회)
- [ ] 3) 결과 수집 및 집계
- [ ] 4) 대시보드 렌더링 (format에 따라)
- [ ] 5) 출처 및 신뢰도 정보 첨부
```

---

## 입력 파싱 규칙

사용자 입력에서 아래 정보를 추출한다:

```
company_names: list[str]   기업명 목록 (1~5개)
format:        str         "table" | "json" | "markdown" | "dashboard" (기본: table)
compare_mode:  bool        복수 기업이면 True 자동 설정
verbose:       bool        상세 로그 출력 여부
```

예시:
```
"삼성전자 분석해줘"
  → company_names=["삼성전자"], compare_mode=False

"삼성전자랑 SK하이닉스 비교해줘"
  → company_names=["삼성전자", "SK하이닉스"], compare_mode=True

"삼성전자 최신 IR 결과를 JSON으로 줘"
  → company_names=["삼성전자"], format="json"
```

---

## 단일 기업 대시보드 렌더링

`format=table` (기본):

```
┌─────────────────────────────────────────────────┐
│  📊 삼성전자  2024Q4  신뢰도: HIGH               │
├────────────┬──────────────┬──────────────────────┤
│  항목      │  값          │  YoY                 │
├────────────┼──────────────┼──────────────────────┤
│  매출      │ 79,097 억원  │  +10.7%              │
│  영업이익  │  6,809 억원  │  -35.0%              │
├────────────┴──────────────┴──────────────────────┤
│  부문별 성과                                      │
│  • DS부문: HBM 수요 확대로 흑자 전환              │
│  • MX/VD: 플래그십 신모델 효과 +8%               │
├──────────────────────────────────────────────────┤
│  가이던스: 2025 상반기 AI 서버 수요 확대 전망      │
│  리스크: 미-중 무역분쟁 반도체 수출 규제           │
├──────────────────────────────────────────────────┤
│  출처: DART 공시 20240115001234 (2024-01-15)      │
└──────────────────────────────────────────────────┘
```

---

## 복수 기업 비교 렌더링 (`compare_mode=True`)

```
┌────────────────┬──────────────┬──────────────┐
│                │  삼성전자    │  SK하이닉스  │
├────────────────┼──────────────┼──────────────┤
│  분기          │  2024Q4      │  2024Q4      │
│  매출          │  79,097억    │  17,573억    │
│  영업이익      │   6,809억    │   5,764억    │
│  매출 YoY      │   +10.7%    │   +93.2%    │
│  영업이익 YoY  │   -35.0%    │    흑자전환  │
│  신뢰도        │  HIGH        │  HIGH        │
└────────────────┴──────────────┴──────────────┘
```

---

## 에러 처리 및 부분 성공

복수 기업 분석 시 일부 실패해도 성공한 항목의 결과는 렌더링:

```python
results = {}
errors = {}
for name in company_names:
    result = run_scenario(name)
    if result["status"] == "success":
        results[name] = result["data"]
    else:
        errors[name] = result["message"]

# 성공 항목 렌더링 후 실패 항목 사유 표시
render_dashboard(results)
if errors:
    render_errors(errors)
```

---

## 출처 투명성 원칙

모든 렌더링 결과 말미에 반드시 포함:
- 공시 접수번호(`rcept_no`) 및 접수일자
- DART 원문 URL
- `data_confidence` 레벨과 의미 설명
- 분석 시점 타임스탬프

---

## 확장 포인트

현재 구현된 시나리오:
- `dart-ir-analyzer-scenario`: DART 공시 기반 IR 분석

향후 추가 가능한 시나리오 (플러그인 방식):
- `sec-edgar-scenario`: 미국 SEC EDGAR 10-Q/10-K 분석
- `earnings-call-scenario`: 실적 발표 컨퍼런스콜 트랜스크립트 분석
- `competitor-benchmark-scenario`: 동종 업계 복수 기업 자동 비교

새 시나리오 추가 시 이 스킬의 입력 파싱 및 렌더링 레이어만 확장하면 됨.

---

## Gotchas

- 기업명 5개 초과 입력 시 처음 5개만 처리하고 사용자에게 알림.
- 단일 기업이라도 `compare_mode=False`는 유지. 불필요한 테이블 확장 방지.
- `verbose=True`이면 각 스킬 호출 시점과 소요 시간을 단계별로 출력.
- 캐시 히트율이 낮은 첫 실행은 전체 45초 내외 소요. 사용자에게 사전 안내.
