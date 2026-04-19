"""
fih — Financial Intelligence Hub CLI

Commands:
  analyze          기업명으로 IR 자료 분석 및 대시보드 출력
  compare          복수 기업 나란히 비교
  serve            FastAPI 분석 서버 실행
  install          AgentSkills 계층 전체 설치
  list-skills      설치된 스킬 목록 확인
  configure        API 키 저장
  cache-clear      파싱/LLM 결과 캐시 삭제
  regression-batch 배치 회귀 테스트
"""

import json
import shutil
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich import box

app = typer.Typer(
    name="fih",
    help="Financial Intelligence Hub — DART IR 분석 CLI (7-layer AgentSkills 포함)",
    add_completion=False,
)
console = Console()

# ── 경로 상수 ──────────────────────────────────────────────
CONFIG_DIR  = Path.home() / ".config" / "fih"
CACHE_DIR   = Path(".fih-cache")
SKILLS_DIR  = Path(__file__).parent.parent / "skills"

SKILL_LAYERS = {
    "L1-root":      ["financial-intelligence-hub"],
    "L2-scenario":  ["dart-ir-analyzer-scenario"],
    "L3-component": ["corpcode-resolver", "context-aware-chunker", "solar-insight-extractor"],
    "L4-utility":   ["dart-api-connector", "output-schema-validator"],
}

ALL_SKILLS = [s for skills in SKILL_LAYERS.values() for s in skills]

TARGET_PATHS = {
    "claude": Path.home() / ".claude"  / "skills",
    "codex":  Path.home() / ".codex"   / "skills",
    "cursor": Path.home() / ".cursor"  / "skills",
}


# ══════════════════════════════════════════════════════════
# analyze
# ══════════════════════════════════════════════════════════
@app.command()
def analyze(
    company_name: str = typer.Argument(..., help="분석할 기업명 (예: 삼성전자)"),
    format: str       = typer.Option("table",  "--format", "-f", help="table | json | markdown"),
    save: Optional[Path] = typer.Option(None,  "--save",   "-s", help="결과 저장 경로 (.json)"),
    cache_only: bool  = typer.Option(False, "--cache-only",      help="캐시된 결과만 사용"),
    verbose:    bool  = typer.Option(False, "--verbose",   "-v", help="단계별 로그 출력"),
):
    """기업명으로 최신 DART IR 자료를 분석해 대시보드로 출력한다."""
    dart_key    = _resolve_key("DART_API_KEY",    "dart_api_key")
    upstage_key = _resolve_key("UPSTAGE_API_KEY", "upstage_api_key")
    if not dart_key or not upstage_key:
        _key_error(); raise typer.Exit(1)

    console.print(f"\n[bold cyan]▶ 분석 시작:[/bold cyan] {company_name}\n")

    result = _run_pipeline(company_name, dart_key, upstage_key, cache_only, verbose)
    _render(result, format, company_name)

    if save:
        save.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"\n[green]✓[/green] 저장 완료: {save}")


# ══════════════════════════════════════════════════════════
# compare
# ══════════════════════════════════════════════════════════
@app.command()
def compare(
    companies:  list[str]    = typer.Argument(..., help="비교할 기업명 목록 (공백 구분, 최대 5개)"),
    format:     str          = typer.Option("table", "--format", "-f"),
    save:       Optional[Path] = typer.Option(None,  "--save", "-s"),
    cache_only: bool         = typer.Option(False, "--cache-only"),
    verbose:    bool         = typer.Option(False, "--verbose", "-v"),
):
    """복수 기업을 나란히 비교 분석한다."""
    if len(companies) > 5:
        console.print("[yellow]최대 5개 기업까지 비교 가능합니다. 처음 5개만 처리합니다.[/yellow]")
        companies = companies[:5]

    dart_key    = _resolve_key("DART_API_KEY",    "dart_api_key")
    upstage_key = _resolve_key("UPSTAGE_API_KEY", "upstage_api_key")
    if not dart_key or not upstage_key:
        _key_error(); raise typer.Exit(1)

    console.print(f"\n[bold cyan]▶ 비교 분석:[/bold cyan] {', '.join(companies)}\n")

    results, errors = {}, {}
    for name in companies:
        r = _run_pipeline(name, dart_key, upstage_key, cache_only, verbose)
        if r.get("status") == "success":
            results[name] = r
        else:
            errors[name] = r.get("message", "알 수 없는 오류")

    if results:
        _render_compare(results, format)
    if errors:
        console.print("\n[bold red]분석 실패[/bold red]")
        for name, msg in errors.items():
            console.print(f"  • {name}: {msg}")

    if save and results:
        save.write_text(
            json.dumps({"results": results, "errors": errors}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        console.print(f"\n[green]✓[/green] 저장 완료: {save}")


# ══════════════════════════════════════════════════════════
# serve
# ══════════════════════════════════════════════════════════
@app.command()
def serve(
    host:   str  = typer.Option("0.0.0.0", help="바인드 호스트"),
    port:   int  = typer.Option(8000,      help="포트 번호"),
    reload: bool = typer.Option(False, "--reload", help="코드 변경 시 자동 재시작"),
):
    """FastAPI 분석 서버를 실행한다. POST /analyze 로 API 호출 가능."""
    import uvicorn
    console.print(f"[bold green]🚀 서버 시작:[/bold green] http://{host}:{port}")
    console.print(f"   Swagger UI: http://{host}:{port}/docs\n")
    uvicorn.run("src.server:app", host=host, port=port, reload=reload)


# ══════════════════════════════════════════════════════════
# install
# ══════════════════════════════════════════════════════════
@app.command()
def install(
    skills:      bool = typer.Option(False, "--skills",      help="AgentSkills 전체 설치"),
    targets:     str  = typer.Option("claude", "--targets",  help="설치 대상 (쉼표 구분): claude,codex,cursor"),
    all_targets: bool = typer.Option(False, "--all-targets", help="모든 에이전트에 설치"),
    layer:       Optional[str] = typer.Option(None, "--layer", help="특정 레이어만 설치: L1,L2,L3,L4"),
    dry_run:     bool = typer.Option(False, "--dry-run",     help="실제 설치 없이 계획만 출력"),
):
    """
    7개 계층형 AgentSkills를 에이전트 환경에 설치한다.

    설치 구조:

    \b
    ~/.claude/skills/
    ├── financial-intelligence-hub/   (L1)
    ├── dart-ir-analyzer-scenario/    (L2)
    ├── corpcode-resolver/            (L3)
    ├── context-aware-chunker/        (L3)
    ├── solar-insight-extractor/      (L3)
    ├── dart-api-connector/           (L4)
    └── output-schema-validator/      (L4)
    """
    if not skills:
        console.print("--skills 플래그를 사용하세요: fih install --skills")
        raise typer.Exit(1)

    # 설치 대상 스킬 결정
    if layer:
        key = layer.upper()
        layer_map = {"L1": "L1-root", "L2": "L2-scenario", "L3": "L3-component", "L4": "L4-utility"}
        if key not in layer_map:
            console.print(f"[red]알 수 없는 레이어:[/red] {layer}  (L1/L2/L3/L4)")
            raise typer.Exit(1)
        target_skills = SKILL_LAYERS[layer_map[key]]
    else:
        target_skills = ALL_SKILLS

    # 설치 대상 에이전트 결정
    target_list = list(TARGET_PATHS.keys()) if all_targets else [t.strip() for t in targets.split(",")]

    # 설치 계획 미리보기
    tree = Tree("[bold]설치 계획[/bold]")
    for agent in target_list:
        if agent not in TARGET_PATHS:
            continue
        branch = tree.add(f"[cyan]{agent}[/cyan]  →  {TARGET_PATHS[agent]}")
        for layer_name, skills_in_layer in SKILL_LAYERS.items():
            layer_branch = branch.add(f"[dim]{layer_name}[/dim]")
            for skill in skills_in_layer:
                if skill in target_skills:
                    src = SKILLS_DIR / skill
                    status = "✓ 준비됨" if src.exists() else "[red]✗ 소스 없음[/red]"
                    layer_branch.add(f"{skill}  {status}")
    console.print(tree)

    if dry_run:
        console.print("\n[yellow]--dry-run: 실제 설치를 수행하지 않았습니다.[/yellow]")
        return

    # 실제 설치
    installed = []
    failed    = []

    for agent in target_list:
        if agent not in TARGET_PATHS:
            console.print(f"[yellow]알 수 없는 에이전트 건너뜀:[/yellow] {agent}")
            continue

        base_dir = TARGET_PATHS[agent]
        base_dir.mkdir(parents=True, exist_ok=True)

        for skill in target_skills:
            src  = SKILLS_DIR / skill
            dest = base_dir   / skill

            if not src.exists():
                failed.append(f"{agent}/{skill} — 소스 없음")
                continue

            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
            installed.append(f"{agent}/{skill}")

    # 결과 출력
    console.print()
    if installed:
        console.print(f"[bold green]✓ 설치 완료[/bold green] ({len(installed)}개)")
        for item in installed:
            console.print(f"  [green]•[/green] {item}")
    if failed:
        console.print(f"\n[bold red]✗ 실패[/bold red] ({len(failed)}개)")
        for item in failed:
            console.print(f"  [red]•[/red] {item}")

    console.print("\n에이전트를 재시작하면 스킬이 활성화됩니다.")
    console.print("[dim]스킬 확인:  fih list-skills[/dim]")


# ══════════════════════════════════════════════════════════
# list-skills
# ══════════════════════════════════════════════════════════
@app.command(name="list-skills")
def list_skills(
    agent: str = typer.Option("claude", "--agent", "-a", help="확인할 에이전트: claude,codex,cursor"),
):
    """설치된 AgentSkills 목록과 레이어 구조를 확인한다."""
    if agent not in TARGET_PATHS:
        console.print(f"[red]알 수 없는 에이전트:[/red] {agent}")
        raise typer.Exit(1)

    base_dir = TARGET_PATHS[agent]
    console.print(f"\n[bold]설치 경로:[/bold] {base_dir}\n")

    t = Table(show_header=True, header_style="bold", box=box.SIMPLE)
    t.add_column("레이어",  style="dim",  width=14)
    t.add_column("스킬명",  style="bold", width=34)
    t.add_column("상태",    width=10)
    t.add_column("SKILL.md 크기", width=14)

    for layer_name, skills in SKILL_LAYERS.items():
        for skill in skills:
            skill_dir  = base_dir / skill
            skill_file = skill_dir / "SKILL.md"
            if skill_dir.exists() and skill_file.exists():
                size   = f"{skill_file.stat().st_size:,} B"
                status = "[green]✓ 설치됨[/green]"
            else:
                size   = "—"
                status = "[red]✗ 없음[/red]"
            t.add_row(layer_name, skill, status, size)

    console.print(t)


# ══════════════════════════════════════════════════════════
# configure
# ══════════════════════════════════════════════════════════
@app.command()
def configure():
    """DART_API_KEY, UPSTAGE_API_KEY를 로컬에 저장한다."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    cfg_file = CONFIG_DIR / "config.json"
    existing = json.loads(cfg_file.read_text()) if cfg_file.exists() else {}

    dart_key    = typer.prompt("DART_API_KEY",    default=existing.get("dart_api_key",    ""), hide_input=True)
    upstage_key = typer.prompt("UPSTAGE_API_KEY", default=existing.get("upstage_api_key", ""), hide_input=True)

    cfg_file.write_text(
        json.dumps({"dart_api_key": dart_key, "upstage_api_key": upstage_key}, indent=2)
    )
    cfg_file.chmod(0o600)
    console.print(f"[green]✓[/green] 저장 완료: {cfg_file}")


# ══════════════════════════════════════════════════════════
# cache-clear
# ══════════════════════════════════════════════════════════
@app.command(name="cache-clear")
def cache_clear(
    scope:   str  = typer.Argument("all", help="all | corp | parse | llm"),
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    """파싱/LLM/corp_code 캐시를 삭제한다."""
    scopes = ["corp", "parse", "llm"] if scope == "all" else [scope]
    total  = 0

    for s in scopes:
        d = CACHE_DIR / s
        if not d.exists():
            continue
        files = list(d.glob("*.json"))
        for f in files:
            console.print(f"  {'[dim][dry][/dim]' if dry_run else '[red][삭제][/red]'} {f.name}")
            if not dry_run:
                f.unlink()
        total += len(files)

    console.print(f"\n총 {total}개 {'확인됨' if dry_run else '삭제됨'}.")


# ══════════════════════════════════════════════════════════
# regression-batch
# ══════════════════════════════════════════════════════════
@app.command(name="regression-batch")
def regression_batch(
    manifest:    Optional[Path] = typer.Option(None, "--manifest",  help="기업 목록 JSON"),
    out_dir:     Path           = typer.Option(Path("tmp/regression"), "--out-dir"),
    limit:       int            = typer.Option(10,   "--limit"),
    assert_pass: bool           = typer.Option(False, "--assert",    help="실패 시 exit(1)"),
    resume:      bool           = typer.Option(False, "--resume",    help="기존 결과 건너뜀"),
    cache_only:  bool           = typer.Option(False, "--cache-only"),
):
    """Manifest의 기업 목록을 순차 분석하고 결과를 저장한다."""
    from src.regression import run_batch
    run_batch(manifest, out_dir, limit, assert_pass, resume, cache_only)


# ══════════════════════════════════════════════════════════
# 헬퍼
# ══════════════════════════════════════════════════════════
def _resolve_key(env_var: str, cfg_key: str) -> Optional[str]:
    import os
    v = os.environ.get(env_var)
    if v:
        return v
    cfg = CONFIG_DIR / "config.json"
    if cfg.exists():
        return json.loads(cfg.read_text()).get(cfg_key)
    return None


def _key_error():
    console.print("[red]API 키가 설정되지 않았습니다.[/red]")
    console.print("  환경변수를 설정하거나 [bold]fih configure[/bold] 를 먼저 실행하세요.\n")
    console.print("  export DART_API_KEY=your_dart_key")
    console.print("  export UPSTAGE_API_KEY=your_upstage_key")


def _run_pipeline(name, dart_key, upstage_key, cache_only, verbose) -> dict:
    try:
        from src.pipeline import run_pipeline
        return run_pipeline(name, dart_key, upstage_key, cache_only, verbose)
    except ImportError:
        import httpx
        try:
            resp = httpx.post(
                "http://localhost:8000/analyze",
                json={"company_name": name},
                timeout=120,
            )
            return resp.json()
        except Exception as e:
            return {"status": "error", "error_code": "CONNECTION_ERROR", "message": str(e)}


def _render(result: dict, format: str, name: str):
    if result.get("status") == "error":
        console.print(Panel(
            f"[red]{result.get('error_code')}[/red]\n{result.get('message')}",
            title=f"분석 실패 — {name}", border_style="red",
        ))
        return

    data = result.get("data", {})
    meta = result.get("meta", {})

    if format == "json":
        from rich.syntax import Syntax
        console.print(Syntax(json.dumps(result, ensure_ascii=False, indent=2), "json", theme="monokai"))
        return

    if format == "markdown":
        _render_md(data, meta)
        return

    # table (기본)
    conf_color = {"high": "green", "medium": "yellow", "low": "red"}.get(
        data.get("data_confidence", "low"), "white"
    )
    console.print(Panel(
        f"[bold]{data.get('company_name', name)}[/bold]  "
        f"[dim]{data.get('report_period', '-')}[/dim]  "
        f"신뢰도: [{conf_color}]{data.get('data_confidence','?').upper()}[/{conf_color}]",
        title="📊 IR 분석 결과", border_style="cyan",
    ))

    t = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
    t.add_column("항목",    style="bold", width=12)
    t.add_column("값",                   width=20)
    t.add_column("YoY",                  width=10)

    for label, key in [("매출", "revenue"), ("영업이익", "operating_income")]:
        d = data.get(key) or {}
        t.add_row(label,
                  f"{d.get('current', '-')} {d.get('unit', '')}",
                  _fmt_pct(d.get("yoy_change_pct")))
    console.print(t)

    if data.get("segment_performance"):
        console.print("[bold]부문별 성과[/bold]")
        for seg in data["segment_performance"]:
            console.print(f"  • [cyan]{seg['segment']}[/cyan]: {seg['summary']}")

    if data.get("guidance"):
        console.print(f"\n[bold]가이던스[/bold]\n  {data['guidance']}")

    if data.get("risk_factors"):
        console.print("\n[bold]리스크[/bold]")
        for r in data["risk_factors"]:
            console.print(f"  ⚠ {r}")

    console.print(f"\n[dim]출처: {meta.get('source_url', '-')}[/dim]")


def _render_compare(results: dict, format: str):
    names = list(results.keys())

    if format == "json":
        from rich.syntax import Syntax
        console.print(Syntax(json.dumps(results, ensure_ascii=False, indent=2), "json", theme="monokai"))
        return

    t = Table(show_header=True, header_style="bold", box=box.SIMPLE_HEAD)
    t.add_column("항목", style="bold", width=14)
    for name in names:
        t.add_column(name, width=18)

    rows = [
        ("분기",          lambda d: d.get("report_period", "-")),
        ("매출",          lambda d: f"{(d.get('revenue') or {}).get('current', '-')} {(d.get('revenue') or {}).get('unit','')}"),
        ("영업이익",      lambda d: f"{(d.get('operating_income') or {}).get('current', '-')} {(d.get('operating_income') or {}).get('unit','')}"),
        ("매출 YoY",      lambda d: _fmt_pct_plain((d.get('revenue') or {}).get('yoy_change_pct'))),
        ("영업이익 YoY",  lambda d: _fmt_pct_plain((d.get('operating_income') or {}).get('yoy_change_pct'))),
        ("신뢰도",        lambda d: (d.get("data_confidence") or "-").upper()),
    ]

    for label, fn in rows:
        t.add_row(label, *[fn(results[n].get("data", {})) for n in names])

    console.print(Panel(t, title="📊 기업 비교 분석", border_style="cyan"))


def _render_md(data: dict, meta: dict):
    rev = data.get("revenue") or {}
    oi  = data.get("operating_income") or {}
    lines = [
        f"# {data.get('company_name', '-')} — {data.get('report_period', '-')}",
        f"\n**신뢰도**: {data.get('data_confidence', '-').upper()}",
        "\n## 재무 요약",
        "| 항목 | 값 | YoY |",
        "|------|-----|-----|",
        f"| 매출 | {rev.get('current','-')} {rev.get('unit','')} | {_fmt_pct_plain(rev.get('yoy_change_pct'))} |",
        f"| 영업이익 | {oi.get('current','-')} {oi.get('unit','')} | {_fmt_pct_plain(oi.get('yoy_change_pct'))} |",
    ]
    if data.get("guidance"):
        lines += ["\n## 가이던스", data["guidance"]]
    if data.get("risk_factors"):
        lines += ["\n## 리스크"] + [f"- {r}" for r in data["risk_factors"]]
    lines += [f"\n---\n출처: {meta.get('source_url', '-')}"]
    console.print("\n".join(lines))


def _fmt_pct(v) -> str:
    if v is None: return "-"
    c = "green" if v >= 0 else "red"
    return f"[{c}]{'+' if v>=0 else ''}{v:.1f}%[/{c}]"

def _fmt_pct_plain(v) -> str:
    if v is None: return "-"
    return f"{'+' if v>=0 else ''}{v:.1f}%"


if __name__ == "__main__":
    app()
