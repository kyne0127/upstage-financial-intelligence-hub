---
name: dart-api-connector
description: |
  DART Open API 엔드포인트 명세, 인증, 공시 유형 코드, 응답 status 코드를 관리하는 유틸리티 스킬.
  다른 스킬이 DART API를 호출하기 전에 반드시 이 스킬을 참조하여 올바른 파라미터와 에러 처리 방법을 확인한다.
  "DART API", "공시 목록 조회", "corp_code", "rcept_no", "pblntf_ty" 등 DART API 파라미터가
  언급될 때 이 스킬을 활성화할 것.
compatibility: 인터넷 접근 필수. DART_API_KEY 환경변수 필요.
metadata:
  layer: "L4-utility"
  version: "1.0"
allowed-tools: [Bash]
---

# DART API Connector

DART Open API 호출에 필요한 모든 명세를 제공하는 유틸리티 스킬.
상위 스킬(`dart-ir-analyzer-scenario`, `corpcode-resolver`)이 이 스킬을 참조한다.

---

## Base URL 및 인증

```
Base URL: https://opendart.fss.or.kr/api
인증:     모든 요청에 crtfc_key 쿼리 파라미터 필수
키 해결:  환경변수 DART_API_KEY → ~/.config/dart-ir/config.json 순서
```

---

## 핵심 엔드포인트

### 1. 공시 목록 조회 (`/list.json`)

```
GET https://opendart.fss.or.kr/api/list.json

필수 파라미터:
  crtfc_key      API 인증키
  corp_code      8자리 기업 고유번호

선택 파라미터:
  pblntf_ty      공시 유형 코드 (하단 코드표 참조)
  pblntf_detail_ty  세부 유형 코드
  page_count     페이지당 건수 (최대 100, 기본 10)
  sort           정렬 기준: "date" (기본)
  sort_mth       정렬 방향: "desc" (기본)

응답 필드:
  status         결과 코드 ("000" = 정상)
  list[].rcept_no    14자리 접수번호 (문자열, 선행 0 보존)
  list[].corp_name   기업명
  list[].report_nm   보고서명
  list[].rcept_dt    접수일자 (YYYYMMDD)
```

### 2. 기업 코드 다운로드 (`/corpCode.xml`)

```
GET https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={key}

응답: ZIP 바이너리 → CORPCODE.xml 포함
XML 구조: <list><item>
  <corp_code>00126380</corp_code>
  <corp_name>삼성전자</corp_name>
  <stock_code>005930</stock_code>
  <modify_date>20240101</modify_date>
</item></list>
```

---

## 공시 유형 코드표

| pblntf_ty | 유형명 | IR 적합도 |
|-----------|--------|----------|
| `F` | 공정공시 | ★★★ 주 타겟 |
| `A` | 정기공시 | ★★ 분기/사업보고서 |
| `B` | 주요사항보고 | ★ 참고용 |

### 세부 유형 (pblntf_ty=F)

| pblntf_detail_ty | 세부명 | 우선순위 |
|-----------------|--------|---------|
| `F001` | 영업(잠정)실적(공정공시) | 1순위 |
| `F004` | 분기 영업(잠정)실적(공정공시) | 2순위 |
| `F003` | 연간 영업(잠정)실적(공정공시) | 3순위 |
| `F002` | 주요경영사항(공정공시) | 4순위 |

**탐색 전략**: F001 → F004 → F003 → F002 순서로 시도. 각 시도에서
`list`가 비어있으면 다음 유형으로 이동.

---

## 응답 status 코드

| status | 의미 | 처리 방법 |
|--------|------|---------|
| `000` | 정상 | 계속 진행 |
| `010` | API 키 오류 | DART_API_KEY 확인 |
| `011` | 사용 한도 초과 | 재시도 또는 알림 |
| `013` | IP 제한 | 요청 간격 조절 |
| `020` | 없는 공시 | NO_DISCLOSURE 에러 반환 |
| `100` | 필수 파라미터 누락 | 파라미터 확인 |

---

## Gotchas

- `rcept_no`는 14자리 **문자열**. 선행 0이 있을 수 있으므로 int 변환 금지.
- DART 서버는 연속 요청 시 IP 차단 가능. 요청 간 `time.sleep(0.5)` 권장.
- `CORPCODE.xml`은 월 단위로 갱신됨. 서버 기동 시 1회 로드 후 캐시 사용.
- `list`가 없는 응답도 `status=000`일 수 있음 — `list` 필드 존재 여부를 별도 확인.
