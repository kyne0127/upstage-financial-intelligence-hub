"""server.py — FastAPI 엔트리포인트"""
import json, os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

corp_map: dict = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global corp_map
    try:
        from src.pipeline import _load_corp_map
        from src.cache import Cache
        corp_map = _load_corp_map(os.environ.get("DART_API_KEY",""), Cache())
    except Exception as e:
        print(f"[warn] corp_map 로드 실패: {e}")
    yield

app = FastAPI(title="Financial Intelligence Hub API", version="0.1.0", lifespan=lifespan)

class IRRequest(BaseModel):
    company_name: str

@app.post("/analyze")
async def analyze(req: IRRequest):
    from src.pipeline import run_pipeline
    result = run_pipeline(
        req.company_name,
        os.environ.get("DART_API_KEY",""),
        os.environ.get("UPSTAGE_API_KEY",""),
    )
    return JSONResponse(result)

@app.get("/health")
def health():
    return {"status": "ok", "corp_map_size": len(corp_map)}

@app.get("/skills")
def list_skills():
    """설치된 스킬 목록 반환"""
    from pathlib import Path
    skills_dir = Path(__file__).parent.parent / "skills"
    skills = []
    for d in sorted(skills_dir.iterdir()):
        if d.is_dir() and (d / "SKILL.md").exists():
            fm = _read_frontmatter(d / "SKILL.md")
            skills.append({"name": d.name, "layer": fm.get("layer","?")})
    return {"skills": skills}

def _read_frontmatter(path) -> dict:
    import re
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m: return {}
    result = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip().strip('"')
    return result
