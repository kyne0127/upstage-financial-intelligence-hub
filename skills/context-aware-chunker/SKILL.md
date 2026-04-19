---
name: context-aware-chunker
description: |
  Upstage Document Parse로 변환된 IR PDF Markdown 텍스트에서 재무 관련 섹션을 추출하고,
  LLM 컨텍스트 윈도우 제한(32,000자)에 맞게 슬라이딩 윈도우 청킹을 수행하는 컴포넌트 스킬.
  "청킹", "컨텍스트 관리", "섹션 추출", "마크다운 파싱", "LLM 입력 최적화" 등이 언급될 때
  활성화할 것. dart-ir-analyzer-scenario의 Step 3에서 호출된다.
metadata:
  layer: "L3-component"
  version: "1.0"
allowed-tools: [Bash]
---

# Context-Aware Chunker

IR Markdown에서 재무 섹션을 우선 추출하고 LLM 입력 크기를 최적화하는 컴포넌트 스킬.

---

## 입력 / 출력

```
입력: markdown: str     (Document Parse 출력 원문)
출력: list[TextChunk]   (인덱스 부여된 청크 리스트)

TextChunk {
  text:    str   (실제 입력 텍스트)
  index:   int   (0-based)
  total:   int   (전체 청크 수)
}
```

---

## 처리 파이프라인

```
원문 Markdown
     │
     ▼
[1단계] 헤더 기반 섹션 분리
     │  re.split(r"(?=^#{1,3} )", markdown, flags=re.MULTILINE)
     │
     ▼
[2단계] 재무 키워드 섹션 필터링
     │  평균 40~60% 텍스트 제거
     │
     ▼
[3단계] 길이 판단
     │  ≤ 32,000자 → 단일 청크 반환
     │  > 32,000자 → 슬라이딩 윈도우 분할
     │
     ▼
list[TextChunk]
```

---

## 재무 키워드 목록

```python
FINANCE_KEYWORDS = [
    "매출", "영업이익", "영업손익", "순이익", "당기순이익",
    "실적", "가이던스", "전망", "리스크", "사업부문", "부문별",
    "연결", "별도", "잠정", "재무", "손익", "성장률",
    "revenue", "operating income", "guidance", "outlook",
]
```

섹션의 헤더 또는 본문에 키워드가 1개 이상 포함되면 선택.

---

## 슬라이딩 윈도우 파라미터

```python
MAX_CHARS   = 32_000   # 전체 제한
CHUNK_SIZE  = 12_000   # 청크 크기
OVERLAP     =  1_000   # 청크 간 중복 (문맥 연속성 보장)
```

오버랩의 목적: 재무 수치가 섹션 경계에 걸쳐 있을 때 어느 청크에서도 캡처 가능하도록.

---

## 복수 청크 결과 병합 규칙

```python
def merge_results(results: list[dict]) -> dict:
    merged = results[0].copy()
    for r in results[1:]:
        # null 필드는 이후 청크로 보완
        for key in ["revenue", "operating_income", "guidance"]:
            if merged.get(key) is None and r.get(key) is not None:
                merged[key] = r[key]
        # segment_performance 누적 (중복 제거)
        existing = {s["segment"] for s in merged.get("segment_performance", [])}
        for seg in r.get("segment_performance", []):
            if seg["segment"] not in existing:
                merged["segment_performance"].append(seg)
        # risk_factors 누적 (중복 제거)
        existing_r = set(merged.get("risk_factors", []))
        for risk in r.get("risk_factors", []):
            if risk not in existing_r:
                merged["risk_factors"].append(risk)
    return merged
```

---

## Gotchas

- 헤더 없는 IR PDF: 섹션 분리 실패 → 전체 텍스트를 키워드 기준 substring으로 재시도.
- 키워드 매칭 섹션이 0개: 원문 전체를 MAX_CHARS까지 잘라 반환 (필터링 포기).
- 청크 수 > 5이면 비용·레이턴시 급증 경고 로그 출력. 10 초과 시 첫 5개만 처리.
- `오버랩` 텍스트에서 같은 수치가 두 번 추출되면 `merge_results`의 첫 번째 값 우선.
