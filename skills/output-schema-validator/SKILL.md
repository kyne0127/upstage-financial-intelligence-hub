---
name: output-schema-validator
description: |
  dart-ir-analyzer 파이프라인의 최종 JSON 출력이 정의된 AgentSkills 표준 스펙을 준수하는지
  검증하는 유틸리티 스킬. LLM 분석 결과를 반환하기 전 반드시 이 스킬의 스키마로 검증해야 한다.
  "결과 검증", "JSON 스키마", "data_confidence", "output-schema", "응답 포맷 확인" 등이
  언급될 때 이 스킬을 활성화할 것.
metadata:
  layer: "L4-utility"
  version: "1.0"
allowed-tools: [Bash]
---

# Output Schema Validator

LLM 추출 결과가 표준 스펙을 준수하는지 검증하고, 위반 시 보정 지침을 제공하는 유틸리티 스킬.

---

## 성공 응답 스키마

```json
{
  "skill": "dart-ir-analyzer",
  "status": "success",
  "data": {
    "company_name":     "string (필수)",
    "report_period":    "string (필수, 예: 2024Q4 / 2024H1 / 2024FY)",
    "revenue": {
      "current":        "number | null",
      "yoy_change_pct": "number | null  (증가 +, 감소 -)",
      "unit":           "string (필수, 예: 억원 / 백만원)"
    },
    "operating_income": {
      "current":        "number | null",
      "yoy_change_pct": "number | null",
      "unit":           "string (필수)"
    },
    "segment_performance": [
      { "segment": "string", "summary": "string (2~3문장)" }
    ],
    "guidance":         "string | null",
    "risk_factors":     ["string"],
    "data_confidence":  "\"high\" | \"medium\" | \"low\" (필수)"
  },
  "meta": {
    "rcept_no":   "string (필수)",
    "rcept_dt":   "string YYYYMMDD (필수)",
    "report_nm":  "string (필수)",
    "source_url": "string URL (필수)"
  }
}
```

## 에러 응답 스키마

```json
{
  "skill": "dart-ir-analyzer",
  "status": "error",
  "error_code": "CORP_NOT_FOUND | NO_DISCLOSURE | NO_PDF_ATTACHMENT | PARSE_FAILED | LLM_PARSE_ERROR | CACHE_MISS",
  "message": "string (한국어 실패 사유)"
}
```

---

## 검증 규칙 체크리스트

```
필수 필드
- [ ] skill == "dart-ir-analyzer"
- [ ] status in ("success", "error")
- [ ] data.company_name 비어있지 않음
- [ ] data.report_period 비어있지 않음
- [ ] data.revenue.unit 비어있지 않음 (current가 null이어도 unit 필수)
- [ ] data.operating_income.unit 비어있지 않음
- [ ] data.data_confidence in ("high", "medium", "low")
- [ ] meta.rcept_no 14자리 문자열
- [ ] meta.source_url "https://dart.fss.or.kr" 로 시작

타입 규칙
- [ ] revenue.current → number 또는 null (빈 문자열 "" 불허)
- [ ] yoy_change_pct → number 또는 null (퍼센트, 소수 허용)
- [ ] segment_performance → 배열 (비어있어도 됨, null 불허)
- [ ] risk_factors → 배열 (비어있어도 됨, null 불허)

data_confidence 기준
- [ ] high:   revenue.current AND operating_income.current 모두 non-null
- [ ] medium: 둘 중 하나만 non-null 또는 추정값 포함
- [ ] low:    수치 대부분 null, 텍스트 기반 추정
```

---

## 보정 지침 (검증 실패 시)

| 위반 유형 | 보정 방법 |
|---------|---------|
| 빈 문자열 `""` → 수치 필드 | `null`로 교체 |
| `segment_performance: null` | `[]`로 교체 |
| `risk_factors: null` | `[]`로 교체 |
| `yoy_change_pct: "10%"` (문자열) | 숫자 `10.0`으로 변환 |
| `data_confidence` 누락 | 규칙 적용 후 자동 부여 |
| `unit` 누락 | IR 텍스트에서 재추출, 불명확 시 `"억원"` 기본값 |

---

## Gotchas

- LLM은 종종 `null` 대신 `"N/A"`, `"-"`, `""` 를 반환한다. 모두 `null`로 정규화.
- `yoy_change_pct`는 소수점 1자리로 반올림. `-35.047` → `-35.0`.
- `report_period` 형식: `2024Q4` (분기), `2024H1` (반기), `2024FY` (연간).
  LLM이 `"2024년 4분기"` 형태로 반환하면 `2024Q4`로 변환.
