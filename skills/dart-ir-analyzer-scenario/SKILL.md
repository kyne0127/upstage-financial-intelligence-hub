---
name: dart-ir-analyzer-scenario
description: |
  DART IR 분석 전체 파이프라인을 관장하는 시나리오 스킬. 기업 코드 탐색부터 LLM 분석,
  결과 검증까지 6단계 워크플로우를 오케스트레이션한다. 하위 컴포넌트 스킬
  (corpcode-resolver, context-aware-chunker, solar-insight-extractor)과 유틸리티 스킬
  (dart-api-connector, output-schema-validator)을 순서에 맞게 호출한다.
  "IR 분석 파이프라인", "DART 전체 흐름", "공시 분석 실행", "실적 분석 워크플로우" 등이
  언급될 때 활성화할 것. financial-intelligence-hub의 L2 시나리오로 작동한다.
compatibility: Python 3.10+, DART_API_KEY, UPSTAGE_API_KEY, 인터넷 접근 필수
metadata:
  layer: "L2-scenario"
  version: "1.0"
allowed-tools: [Bash]
---

# DART IR Analyzer Scenario

6단계 파이프라인의 오케스트레이터. 각 단계에서 적절한 하위 스킬을 호출하고
실패 시 즉시 에러 응답을 반환하는 Fail-Fast 전략을 적용한다.

참조 스킬:
- `dart-api-connector` — DART API 명세 (L4)
- `output-schema-validator` — 출력 스키마 (L4)
- `corpcode-resolver` — 기업명 → corp_code (L3)
- `context-aware-chunker` — IR 텍스트 청킹 (L3)
- `solar-insight-extractor` — LLM 인사이트 추출 (L3)

---

## 워크플로우 체크리스트

```
- [ ] Step 1: CorpCode_Resolver → corp_code 획득
- [ ] Step 2: DART_API_Connector → rcept_no 획득
- [ ] Step 3: PDF URL 추출 (3단계 폴백 스크래핑)
- [ ] Step 4: Upstage Document Parse → Markdown 변환
- [ ] Step 5: Context_Aware_Chunker + Solar_Insight_Extractor → JSON
- [ ] Step 6: Output_Schema_Validator 검증 → 표준 응답 반환
```

각 단계 실패 시 즉시 중단하고 `output-schema-validator`의 에러 응답 스키마로 반환.

---

## Step 1: corp_code 획득

`corpcode-resolver` 스킬 호출:
```
입력: company_name
출력: corp_code (8자리) 또는 CORP_NOT_FOUND 에러
```

---

## Step 2: 공시 목록 조회 및 rcept_no 획득

`dart-api-connector` 스킬의 탐색 전략(F001→F004→F003→F002) 적용:
```
입력: corp_code
출력: (rcept_no, rcept_dt, report_nm) 또는 NO_DISCLOSURE 에러
```

---

## Step 3: PDF URL 추출

DART 뷰어 HTML 스크래핑. 3단계 폴백 순서:
```
1. viewDoc() JS 파싱 → dcmNo 추출
2. getSubOrd.do 첨부파일 API
3. HTML <a> 태그 직접 탐색
→ 모두 실패 시: NO_PDF_ATTACHMENT 에러
```

HWP 파일만 있는 경우도 NO_PDF_ATTACHMENT로 처리.

상세 스크래핑 패턴: `dart-ir-analyzer` 레포의 `references/dart-scraping.md` 참조.

---

## Step 4: Upstage Document Parse

```python
POST https://api.upstage.ai/v1/document-ai/document-parse
  document: (binary PDF)
  output_formats: '["markdown"]'
  ocr: "auto"
  timeout: 120s

→ markdown: str (레이아웃 보존 Markdown)
→ 실패 시: PARSE_FAILED 에러
```

결과를 캐시에 저장 (키: rcept_no, scope: "parse").

---

## Step 5: 청킹 + LLM 분석

`context-aware-chunker` 스킬로 청킹 후 `solar-insight-extractor` 스킬 호출:
```
markdown → chunks → [LLM 분석 × n] → 병합 결과
→ 실패 시: LLM_PARSE_ERROR 에러
```

---

## Step 6: 검증 및 응답 반환

`output-schema-validator` 스킬로 검증 후 보정:
```python
validated = validator.validate_and_fix(analysis)
return {
    "skill": "dart-ir-analyzer",
    "status": "success",
    "data": validated,
    "meta": {
        "rcept_no": rcept_no,
        "rcept_dt": rcept_dt,
        "report_nm": report_nm,
        "source_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}",
    }
}
```

---

## Fail-Fast 에러 매트릭스

| 단계 | 실패 조건 | error_code |
|------|---------|-----------|
| Step 1 | corp_code 매핑 실패 | `CORP_NOT_FOUND` |
| Step 2 | 공시 없음 / DART API 오류 | `NO_DISCLOSURE` / `DART_API_ERROR` |
| Step 3 | PDF URL 없음 | `NO_PDF_ATTACHMENT` |
| Step 4 | Document Parse 실패 | `PARSE_FAILED` |
| Step 5 | LLM JSON 파싱 실패 | `LLM_PARSE_ERROR` |
| Step 6 | 검증 후 보정 불가 | `SCHEMA_VIOLATION` |

---

## Gotchas

- Step 3~4는 캐시 우선 확인. 동일 `rcept_no`가 캐시에 있으면 Step 4 건너뜀.
- Step 5에서 청크 수 > 5이면 비용 경고 로그. 상위 스킬에 전달.
- Step 2의 DART API 호출은 `dart-api-connector` 명세의 IP 차단 주의사항 준수.
