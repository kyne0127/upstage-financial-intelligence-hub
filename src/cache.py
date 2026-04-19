"""cache.py — 로컬 파일 캐시"""
import json
from pathlib import Path
from typing import Any, Optional

CACHE_DIR = Path(".fih-cache")

class Cache:
    def get(self, scope: str, key: str) -> Optional[Any]:
        try:
            return json.loads(self._path(scope, key).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def set(self, scope: str, key: str, value: Any):
        p = self._path(scope, key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def _path(self, scope: str, key: str) -> Path:
        return CACHE_DIR / scope / f"{key.replace('/', '_')}.json"
