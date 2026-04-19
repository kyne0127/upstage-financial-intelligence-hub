"""chunker.py"""
import re
from dataclasses import dataclass, field

FINANCE_KEYWORDS = ["매출","영업이익","영업손익","순이익","실적","가이던스","전망",
                    "리스크","사업부문","부문별","연결","별도","잠정","재무","손익"]
MAX_CHARS, CHUNK_SIZE, OVERLAP = 32_000, 12_000, 1_000

@dataclass
class TextChunk:
    text: str; index: int; total: int

def prepare_for_llm(markdown: str) -> list[TextChunk]:
    sections = re.split(r"(?=^#{1,3} )", markdown, flags=re.MULTILINE)
    sel = "\n\n".join(s for s in sections if any(k in s for k in FINANCE_KEYWORDS)) or markdown
    if len(sel) <= MAX_CHARS:
        return [TextChunk(sel, 0, 1)]
    chunks = [sel[i:i+CHUNK_SIZE] for i in range(0, len(sel), CHUNK_SIZE - OVERLAP)]
    return [TextChunk(c, i, len(chunks)) for i, c in enumerate(chunks)]

def merge_results(results: list[dict]) -> dict:
    if not results: return {}
    m = results[0].copy()
    for r in results[1:]:
        for k in ["revenue", "operating_income", "guidance"]:
            if m.get(k) is None and r.get(k) is not None: m[k] = r[k]
        ex = {s["segment"] for s in m.get("segment_performance", [])}
        for s in r.get("segment_performance", []):
            if s["segment"] not in ex: m.setdefault("segment_performance",[]).append(s)
        er = set(m.get("risk_factors", []))
        for rf in r.get("risk_factors", []):
            if rf not in er: m.setdefault("risk_factors",[]).append(rf)
    return m
