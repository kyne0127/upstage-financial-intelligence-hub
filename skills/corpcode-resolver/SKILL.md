---
name: corpcode-resolver
description: |
  사용자가 입력한 기업명(또는 ticker)을 DART 표준 corp_code(8자리)로 변환하는 컴포넌트 스킬.
  Fuzzy Matching을 적용해 정확하지 않은 기업명도 처리한다.
  "기업 코드 찾기", "corp_code 변환", "DART 기업 식별자", "기업명 매핑", "ticker 변환" 등이
  언급될 때 활성화할 것. dart-ir-analyzer-scenario의 Step 1에서 호출된다.
compatibility: Python 3.10+, DART_API_KEY 필요, 인터넷 접근 필수 (초기 로드 시)
metadata:
  layer: "L3-component"
  version: "1.0"
allowed-tools: [Bash]
---

# CorpCode Resolver

기업명 → DART corp_code 변환 컴포넌트.
`dart-api-connector` 스킬의 CORPCODE.xml 명세를 참조한다.

---

## 입력 / 출력

```
입력: company_name: str  (예: "삼성전자", "samsung", "005930")
출력: corp_code: str     (예: "00126380")
      None               (매핑 실패 시)
```

---

## 매핑 전략 (우선순위 순)

### 1단계: 정확 일치 (O(1))
```python
if company_name in corp_map:
    return corp_map[company_name]
```

### 2단계: 접두 일치
```python
for name, code in corp_map.items():
    if name.startswith(company_name):
        return code
```

### 3단계: 포함 일치
```python
for name, code in corp_map.items():
    if company_name in name:
        return code
```

### 4단계: ticker(종목코드) 직접 입력 처리
```python
# 6자리 숫자면 ticker로 간주 → stock_code 역매핑
if re.match(r'^\d{6}$', company_name):
    for name, meta in corp_map_with_stock.items():
        if meta['stock_code'] == company_name:
            return meta['corp_code']
```

### 5단계: 매핑 실패
```
에러 코드: CORP_NOT_FOUND
메시지: "기업명을 찾을 수 없습니다: {company_name}"
```

---

## CORPCODE.xml 로드 로직

```python
import io, zipfile, xml.etree.ElementTree as ET
import requests

def load_corpcode(api_key: str) -> dict[str, str]:
    """corp_name → corp_code 딕셔너리 반환. 약 10만 건."""
    url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={api_key}"
    resp = requests.get(url, timeout=30)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        xml_bytes = z.read("CORPCODE.xml")
    root = ET.fromstring(xml_bytes)
    return {
        item.findtext("corp_name", "").strip(): item.findtext("corp_code", "").strip()
        for item in root.findall("list")
        if item.findtext("corp_code", "").strip()
    }
```

캐시 전략:
- FastAPI `lifespan`에서 서버 기동 시 1회 로드 → 메모리 유지
- CLI 모드: `~/.dart-ir-cache/corp/corpcode.json` 파일 캐시 (TTL: 168시간)
- 캐시 미스 또는 만료 시 재다운로드

---

## Gotchas

- `corp_name` 필드와 일반 기업명이 다를 수 있음: `"삼성전자"` vs `"삼성전자(주)"`.
  3단계 포함 일치가 이 케이스를 흡수한다.
- 동명이인 기업 존재 시 첫 번째 매칭 반환. 모호성이 높으면 사용자에게 확인 요청.
- CORPCODE.xml은 비상장 법인도 포함 (~100,000건). 상장 여부는 `stock_code` 필드로 구분.
- 영문 입력("samsung")은 한국어 이름 매핑에 실패함. 향후 영문명 역인덱스 추가 예정.
