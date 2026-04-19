---
name: solar-insight-extractor
description: |
  Upstage Solar LLM을 활용하여 IR Markdown 텍스트에서 재무 지표와 정성적 인사이트를
  구조화 JSON으로 추출하는 컴포넌트 스킬. 프롬프트 설계, temperature 설정, JSON 파싱 안정화,
  멀티청크 처리를 담당한다. "Solar LLM", "인사이트 추출", "LLM 분석", "JSON 추출",
  "system_prompt" 등이 언급될 때 활성화할 것. dart-ir-analyzer-scenario의 Step 4에서 호출된다.
compatibility: UPSTAGE_API_KEY 필요, 인터넷 접근 필수
metadata:
  layer: "L3-component"
  version: "1.0"
allowed-tools: [Bash]
---

# Solar Insight Extractor

Solar LLM으로 IR 텍스트를 분석해 구조화 JSON을 추출하는 컴포넌트 스킬.
출력 스키마는 `output-schema-validator` 스킬의 정의를 따른다.

---

## API 호출 명세

```
POST https://api.upstage.ai/v1/solar/chat/completions
Authorization: Bearer {UPSTAGE_API_KEY}
Content-Type: application/json

Body:
{
  "model":       "solar-pro",
  "messages":    [...],
  "temperature": 0.0,
  "max_tokens":  2048
}
```

모델 선택:
- `solar-pro`: 정확도 우선 (기본값)
- `solar-mini`: 속도·비용 우선 (배치 처리 시)

---

## System Prompt 구조

system_prompt.txt에서 로드. 핵심 지침:

```
1. 역할: 전문 재무 애널리스트
2. 출력 형식: 순수 JSON만 (마크다운 펜스, 설명 텍스트 금지)
3. 스키마: output-schema-validator의 data 필드 그대로
4. null 규칙: 찾을 수 없는 값은 0이 아닌 null
5. 수치 단위: 원문 표기 그대로 (억원/백만원 등)
6. 신뢰도: high/medium/low 기준 적용
```

---

## JSON 파싱 안정화

LLM 출력에서 JSON을 안전하게 추출하는 3단계 방어 로직:

```python
import json, re

def safe_parse(raw: str) -> dict:
    # 1단계: 마크다운 코드펜스 제거
    clean = re.sub(r"```(?:json)?|```", "", raw).strip()

    # 2단계: 직접 파싱 시도
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # 3단계: 첫 번째 { ... } 블록 추출
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if match:
        return json.loads(match.group())

    raise json.JSONDecodeError("JSON 블록을 찾을 수 없음", clean, 0)
```

---

## 추출 대상 인사이트

| 항목 | 추출 방식 | 비고 |
|------|---------|------|
| 매출·영업이익 | 수치 + 단위 + YoY% | 표 우선, 텍스트 폴백 |
| 부문별 성과 | 각 사업부문 2~3문장 요약 | 없으면 빈 배열 |
| 가이던스 | 전망·목표 언급 추출 | 없으면 null |
| 리스크 | 명시된 리스크 항목별 1문장 | 없으면 빈 배열 |
| data_confidence | 수치 충족도 자동 판단 | high/medium/low |

---

## 멀티청크 처리 흐름

```python
chunks = context_aware_chunker.prepare(markdown)  # L3 컴포넌트 호출

results = []
for chunk in chunks:
    result = call_solar(chunk.text)
    results.append(result)

final = context_aware_chunker.merge(results)  # 병합도 Chunker에 위임
validated = output_schema_validator.validate(final)  # L4 검증
```

---

## Gotchas

- `temperature: 0.0` 필수. 수치 추출 태스크에서 temperature > 0이면 포맷 불일치 빈발.
- max_tokens < 1024이면 복잡한 부문별 성과 섹션이 잘릴 수 있음. 2048 권장.
- Solar는 한국어 재무 용어에 강하지만, 영문 IR PDF는 정확도가 낮을 수 있음.
- LLM이 `"N/A"`, `"-"`, `"없음"`을 반환하면 `output-schema-validator`가 null로 정규화.
