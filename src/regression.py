"""regression.py — 배치 회귀 테스트"""
import json, os
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

def run_batch(manifest, out_dir, limit, assert_pass, resume, cache_only):
    from src.pipeline import run_pipeline
    dart_key    = os.environ.get("DART_API_KEY", "")
    upstage_key = os.environ.get("UPSTAGE_API_KEY", "")
    out_dir.mkdir(parents=True, exist_ok=True)

    companies = []
    if manifest and Path(manifest).exists():
        data = json.loads(Path(manifest).read_text(encoding="utf-8"))
        companies = data.get("companies", data) if isinstance(data, dict) else data
    else:
        console.print("[red]--manifest 를 지정하세요.[/red]"); return

    companies = companies[:limit]
    passed = failed = skipped = 0

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        task = p.add_task("분석 중...", total=len(companies))
        for item in companies:
            name = item.get("company_name", item.get("name", ""))
            out_file = out_dir / f"{name}.json"
            if resume and out_file.exists():
                skipped += 1; p.advance(task); continue
            p.update(task, description=f"{name} 분석 중...")
            result = run_pipeline(name, dart_key, upstage_key, cache_only=cache_only)
            out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            if result.get("status") == "success" and result.get("data",{}).get("data_confidence") != "low":
                passed += 1
            else:
                failed += 1
            p.advance(task)

    console.print(f"\n결과: [green]{passed}통과[/green] / [red]{failed}실패[/red] / [dim]{skipped}건너뜀[/dim]")
    summary = {"passed": passed, "failed": failed, "skipped": skipped}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    if assert_pass and failed > 0:
        console.print("[red]ASSERT: 실패 항목이 있습니다. exit(1)[/red]")
        raise SystemExit(1)
