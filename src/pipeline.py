"""
pipeline.py
dart-ir-analyzer-repo의 파이프라인을 그대로 재사용.
두 패키지가 함께 설치된 경우 dart_ir_analyzer.pipeline을 import.
단독 사용 시에는 이 파일에 직접 구현체를 둔다.
"""
try:
    from dart_ir_analyzer.pipeline import run_pipeline, _load_corp_map  # noqa: F401
except ImportError:
    # standalone 구현 (dart-ir-analyzer-repo의 pipeline.py 내용과 동일)
    import json, re, time
    from pathlib import Path
    import httpx, requests
    from bs4 import BeautifulSoup
    from src.cache import Cache

    DART_BASE    = "https://opendart.fss.or.kr/api"
    DART_VIEWER  = "https://dart.fss.or.kr"
    UPSTAGE_PARSE = "https://api.upstage.ai/v1/document-ai/document-parse"
    UPSTAGE_SOLAR = "https://api.upstage.ai/v1/solar/chat/completions"
    HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://dart.fss.or.kr/"}

    def run_pipeline(company_name, dart_api_key, upstage_api_key,
                     cache_only=False, verbose=False) -> dict:
        cache = Cache()
        def log(m):
            if verbose: print(f"  {m}")

        log("Step 1: corp_code 매핑")
        corp_map = _load_corp_map(dart_api_key, cache)
        corp_code = _resolve(corp_map, company_name)
        if not corp_code:
            return _err("CORP_NOT_FOUND", f"기업명을 찾을 수 없습니다: {company_name}")

        log("Step 2: DART 공시 조회")
        disc = _fetch_disclosure(corp_code, dart_api_key)
        if not disc:
            return _err("NO_DISCLOSURE", "해당 기업의 공정공시 내역이 없습니다.")
        rcept_no, rcept_dt, report_nm = disc

        cached_md = cache.get("parse", rcept_no)
        if cache_only and not cached_md:
            return _err("CACHE_MISS", f"캐시에 {rcept_no} 없음. --cache-only 없이 재실행하세요.")

        if not cached_md:
            log("Step 3: PDF URL 추출")
            pdf_url = _extract_pdf(rcept_no)
            if not pdf_url:
                return _err("NO_PDF_ATTACHMENT", "최신 공시에 IR 첨부파일(PDF)이 존재하지 않습니다.")
            log("Step 4: Document Parse")
            try:
                markdown = _parse_pdf(pdf_url, upstage_api_key)
                cache.set("parse", rcept_no, markdown)
            except Exception as e:
                return _err("PARSE_FAILED", f"문서 파싱 실패: {e}")
        else:
            log("Step 4: 캐시 히트 (Document Parse 건너뜀)")
            markdown = cached_md

        log("Step 5: Solar LLM 분석")
        from src.chunker import prepare_for_llm, merge_results
        chunks = prepare_for_llm(markdown)
        results = []
        for chunk in chunks:
            ck = f"{rcept_no}_c{chunk.index}"
            cr = cache.get("llm", ck)
            if cr:
                results.append(cr)
            else:
                try:
                    r = _analyze(chunk.text, upstage_api_key)
                    cache.set("llm", ck, r)
                    results.append(r)
                except json.JSONDecodeError as e:
                    return _err("LLM_PARSE_ERROR", f"LLM JSON 파싱 실패: {e}")

        analysis = merge_results(results) if len(results) > 1 else results[0]

        return {
            "skill": "dart-ir-analyzer",
            "status": "success",
            "data": analysis,
            "meta": {
                "rcept_no": rcept_no,
                "rcept_dt": rcept_dt,
                "report_nm": report_nm,
                "source_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}",
            },
        }

    def _err(code, msg):
        return {"skill": "dart-ir-analyzer", "status": "error", "error_code": code, "message": msg}

    def _load_corp_map(api_key, cache):
        cached = cache.get("corp", "corpcode")
        if cached: return cached
        import io, zipfile, xml.etree.ElementTree as ET
        resp = requests.get(f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={api_key}", timeout=30)
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            xml_bytes = z.read("CORPCODE.xml")
        root = ET.fromstring(xml_bytes)
        corp_map = {
            item.findtext("corp_name","").strip(): item.findtext("corp_code","").strip()
            for item in root.findall("list") if item.findtext("corp_code","").strip()
        }
        cache.set("corp", "corpcode", corp_map)
        return corp_map

    def _resolve(corp_map, name):
        if name in corp_map: return corp_map[name]
        for k, v in corp_map.items():
            if k.startswith(name) or name in k: return v
        return None

    def _fetch_disclosure(corp_code, api_key):
        for detail in ["F001", "F004", "F003", "F002", None]:
            params = {"crtfc_key": api_key, "corp_code": corp_code,
                      "pblntf_ty": "F", "page_count": "5", "sort": "date", "sort_mth": "desc"}
            if detail: params["pblntf_detail_ty"] = detail
            data = requests.get(f"{DART_BASE}/list.json", params=params, timeout=15).json()
            if data.get("status") == "000" and data.get("list"):
                i = data["list"][0]
                return i["rcept_no"], i["rcept_dt"], i["report_nm"]
        return None

    def _extract_pdf(rcept_no):
        from urllib.parse import urljoin
        time.sleep(0.5)
        resp = requests.get(f"{DART_VIEWER}/dsaf001/left.do?rcpNo={rcept_no}", headers=HEADERS, timeout=15)
        m = re.findall(r"viewDoc\('(\d+)'", resp.text)
        if m: return f"{DART_VIEWER}/pdf/download/main.do?rcp_no={rcept_no}&dcm_no={m[0]}"
        try:
            for f in requests.get(f"{DART_VIEWER}/dsaf001/getSubOrd.do?rcpNo={rcept_no}",
                                   headers=HEADERS, timeout=15).json():
                if str(f.get("fileNm","")).lower().endswith(".pdf"):
                    return urljoin(DART_VIEWER, f["fileUrl"])
        except Exception: pass
        soup = BeautifulSoup(requests.get(f"{DART_VIEWER}/dsaf001/main.do?rcpNo={rcept_no}",
                                           headers=HEADERS, timeout=15).text, "html.parser")
        for a in soup.find_all("a", href=True):
            if ".pdf" in a["href"].lower(): return urljoin(DART_VIEWER, a["href"])
        return None

    def _parse_pdf(pdf_url, api_key):
        pdf_bytes = requests.get(pdf_url, headers=HEADERS, timeout=60).content
        with httpx.Client(timeout=120) as c:
            r = c.post(UPSTAGE_PARSE,
                       headers={"Authorization": f"Bearer {api_key}"},
                       files={"document": ("ir.pdf", pdf_bytes, "application/pdf")},
                       data={"output_formats": '["markdown"]', "ocr": "auto"})
        r.raise_for_status()
        return r.json()["content"]["markdown"]

    def _analyze(text, api_key):
        prompt_path = Path(__file__).parent.parent / "skills" / "solar-insight-extractor" / "assets" / "system_prompt.txt"
        system = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else (
            "IR 자료에서 핵심 재무 지표를 추출해 순수 JSON만 반환. "
            '스키마: {"company_name","report_period","revenue":{"current","yoy_change_pct","unit"},'
            '"operating_income":{"current","yoy_change_pct","unit"},'
            '"segment_performance":[{"segment","summary"}],"guidance","risk_factors":[],"data_confidence"}'
        )
        with httpx.Client(timeout=60) as c:
            r = c.post(UPSTAGE_SOLAR,
                       headers={"Authorization": f"Bearer {api_key}"},
                       json={"model": "solar-pro", "temperature": 0.0, "max_tokens": 2048,
                             "messages": [{"role": "system", "content": system},
                                          {"role": "user", "content": f"다음 IR 자료:\n\n{text}"}]})
        r.raise_for_status()
        raw = re.sub(r"```(?:json)?|```", "", r.json()["choices"][0]["message"]["content"]).strip()
        return json.loads(raw)
