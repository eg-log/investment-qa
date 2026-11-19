"""서비스 패키지의 구문, 의존성, 저장 파일 무결성을 검사한다."""
import argparse
import ast
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import re
import sys

from model_assets import MODEL_FILES, digest, read_json, validate_model_folder

ROOT = Path(__file__).resolve().parents[1]


def inspect_package():
    source = read_json(ROOT / "source_manifest.json")
    failures, pending = [], []
    paths = [path for path in ROOT.rglob("*") if path.is_file()
             and not any(part in {".git", "__pycache__", ".venv"} for part in path.relative_to(ROOT).parts)]
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if path.suffix == ".py":
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            except SyntaxError as error:
                failures.append("Python 구문 오류: " + relative + " (" + str(error.lineno) + ")")
        if path.suffix.lower() in {".zip", ".pdf"} or path.name.startswith(".env"):
            failures.append("업로드 대상에서 제외해야 할 파일: " + relative)
        if path.stat().st_size > 100_000_000:
            failures.append("100MB 초과 파일: " + relative)
        if path.suffix in {".py", ".md", ".txt", ".json", ".ipynb"}:
            text = path.read_text(encoding="utf-8")
            if re.search(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|hf_[A-Za-z0-9]{30,}|sk-proj-[A-Za-z0-9_-]{30,})", text):
                failures.append("토큰으로 의심되는 문자열이 있는 파일: " + relative)
    notebook = ROOT / "project.ipynb"
    if digest(notebook) != source["source_notebook_sha256"]:
        failures.append("노트북 사본의 SHA256이 최종 원본과 다릅니다.")
    nb = read_json(notebook)
    counts = []
    for index, cell in enumerate(nb["cells"]):
        if cell["cell_type"] == "code":
            text = cell["source"]
            ast.parse("".join(text) if isinstance(text, list) else text)
            counts.append({"cell_index": index, "execution_count": cell.get("execution_count")})
    if counts != source["source_code_execution_counts"]:
        failures.append("원본의 실행 번호가 달라졌습니다.")
    runtime = (ROOT / "persona_runtime.py").read_text(encoding="utf-8")
    nodes = {}
    for node in ast.parse(runtime).body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            nodes[node.name] = ast.get_source_segment(runtime, node)
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            nodes[node.targets[0].id] = ast.get_source_segment(runtime, node)
    import hashlib
    for name, expected in source["runtime_nodes_sha256"].items():
        if hashlib.sha256(nodes.get(name, "").encode()).hexdigest() != expected:
            failures.append("노트북의 기존 추론 정의와 다릅니다: " + name)
    if re.search(r"\.(?:fit|fit_transform)\s*\(", runtime):
        failures.append("추론 코드에 학습 호출이 포함되어 있습니다.")
    for name, expected in source["figures_sha256"].items():
        if digest(ROOT / "reports" / name) != expected:
            failures.append("기존 노트북의 그래프와 다릅니다: " + name)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for link in re.findall(r"\]\(([^)]+)\)", readme):
        if not re.match(r"https?://|#", link) and not (ROOT / link.split("#")[0]).exists():
            failures.append("README 링크의 파일이 없습니다: " + link)
    missing = sorted(name for name in MODEL_FILES if not (ROOT / "models" / name).is_file())
    if missing:
        pending.append("최종 실행의 모델·근거 파일 필요: " + ", ".join(missing))
    else:
        try:
            validate_model_folder(ROOT / "models", ROOT / "source_manifest.json")
        except (ValueError, KeyError, OSError) as error:
            failures.append(str(error))
    environment = {}
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        package, expected = line.split("==")
        try:
            actual = version(package)
        except PackageNotFoundError:
            actual = "not_installed"
        environment[package] = {"required": expected, "actual": actual}
        if expected != actual:
            pending.append("배포 환경 설치 필요: " + line)
    result = {"source_notebook_sha256": digest(notebook), "source_run": source["source_run"],
              "code_checks_passed": not failures, "local_inference_ready": not failures and not pending,
              "code_cells": len(counts), "executed_code_cells": sum(row["execution_count"] is not None for row in counts),
              "notebook_copy_unchanged": digest(notebook) == source["source_notebook_sha256"],
              "failures": failures, "pending": pending, "environment": environment,
              "training_executed_by_check": False, "metrics_recomputed_by_check": False,
              "public_service_tested_by_check": False}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-only", action="store_true", help="코드 검사만 종료 상태에 반영하고 모델·환경 미완료는 결과에 표시합니다.")
    args = parser.parse_args()
    result = inspect_package()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    output = ROOT / "docs/package_check.json"
    if not output.exists():
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.exit(0 if result["code_checks_passed"] and (args.code_only or result["local_inference_ready"]) else 1)
