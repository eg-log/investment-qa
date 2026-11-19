"""실행 노트북에서 추론 정의와 평가 출력을 웹 서비스 파일로 분리한다."""
import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_NOTEBOOK_SHA256 = "bee185049a339265d018a18ed8ac091b8eec50942bc7ea4e11b0708973d97fd9"
RUNTIME_NAMES = ["PERIODS", "LABELS", "digest", "read_json", "ALIASES", "EvidenceChat", "create_gradio"]


def sha(contents):
    return hashlib.sha256(contents).hexdigest()


def source_of(cell):
    value = cell.get("source", "")
    return "".join(value) if isinstance(value, list) else value


def write_new(relative, contents):
    """내용이 다른 기존 파일은 덮어쓰지 않습니다."""
    path = ROOT / relative
    if isinstance(contents, str):
        contents = contents.encode("utf-8")
    if path.exists():
        if path.read_bytes() != contents:
            raise FileExistsError("기존 파일을 보존합니다: " + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)


def json_new(relative, value):
    write_new(relative, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notebook", type=Path, required=True)
    args = parser.parse_args()
    original = args.notebook.resolve()
    content = original.read_bytes()
    if sha(content) != EXPECTED_NOTEBOOK_SHA256:
        raise ValueError("이번에 확인한 최종 project.ipynb와 다릅니다. 원본 변경 여부를 먼저 확인합니다.")
    protected = {p.name: sha(p.read_bytes()) for p in original.parent.iterdir() if p.is_file()}
    notebook = json.loads(content)
    cells = notebook["cells"]
    nodes, plain_outputs, figures, code_counts = {}, [], [], []
    for index, cell in enumerate(cells):
        if cell["cell_type"] != "code":
            continue
        source = source_of(cell)
        code_counts.append({"cell_index": index, "execution_count": cell.get("execution_count")})
        for node in ast.parse(source).body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                nodes[node.name] = ast.get_source_segment(source, node)
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                nodes[node.targets[0].id] = ast.get_source_segment(source, node)
                if node.targets[0].id == "PRINCIPLES":
                    principles = json.loads(ast.literal_eval(node.value.args[0]))
        for output in cell.get("outputs", []):
            if output.get("output_type") == "error":
                raise ValueError("원본 노트북에 오류 출력이 있습니다. 원본은 수정하지 않고 작업을 중단합니다.")
            data = output.get("data", {})
            value = output.get("text", data.get("text/plain", ""))
            plain_outputs.append("".join(value) if isinstance(value, list) else value)
            if "result = train_classifiers(" in source and "image/png" in data:
                value = data["image/png"]
                figures.append(base64.b64decode("".join(value) if isinstance(value, list) else value))
    text = "\n".join(plain_outputs)
    versions, selection, logs, metrics = None, None, [], {}
    for line in text.splitlines():
        if line.startswith("실제 버전:"):
            versions = ast.literal_eval(line.split(":", 1)[1].strip())
        elif line.startswith("검증 선택:"):
            selection = ast.literal_eval(line.split(":", 1)[1].strip())
        elif line.startswith("{'model':"):
            logs.append(ast.literal_eval(line))
        match = re.fullmatch(r"\d+\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+(word_tfidf_logreg|char_tfidf_svm)\s*", line)
        if match:
            metrics[match[5]] = dict(zip(["macro_f1", "accuracy", "macro_precision", "macro_recall"], map(float, match.groups()[:4])))
    runs = re.findall(r"/content/(runs/[^\s]+?)/models", text)
    if not versions or not selection or len(logs) != 6 or len(metrics) != 2 or not runs or len(figures) != 2:
        raise ValueError("최종 노트북의 실행 환경·결과·그래프를 확인할 수 없습니다.")
    runtime = '"""학습한 질문 분류기와 공식 근거를 연결하는 질의응답 및 Gradio 인터페이스."""\n'
    runtime += "from pathlib import Path\nimport hashlib\nimport json\nimport re\nimport time\nimport joblib\n\n"
    runtime += "\n\n".join(nodes[name] for name in RUNTIME_NAMES) + "\n"
    ast.parse(runtime)
    if re.search(r"\.(?:fit|fit_transform)\s*\(", runtime):
        raise ValueError("분리한 추론 코드에 학습 호출이 포함돼 있습니다.")
    write_new("project.ipynb", content)
    write_new("submission.json", (original.parent / "submission.json").read_bytes())
    write_new("persona_runtime.py", runtime)
    write_new("requirements.txt", f"gradio==6.32.0\nscikit-learn=={versions['scikit-learn']}\nnumpy=={versions['numpy']}\npandas=={versions['pandas']}\njoblib=={versions['joblib']}\n")
    json_new("data/principles.json", principles)
    for name, png in zip(["confusion_matrices.png", "validation_comparison.png"], figures):
        write_new("reports/" + name, png)
    write_new("reports/notebook_outputs.txt", text)
    json_new("source_manifest.json", {
        "source_notebook": "project.ipynb", "source_notebook_sha256": sha(content),
        "source_run": runs[-1], "source_versions": versions, "source_cell_count": len(cells),
        "source_code_execution_counts": code_counts, "selected_model": selection["selected_model"],
        "selection": selection, "training_log_from_original_output": logs,
        "test_metrics_from_original_display": metrics,
        "runtime_nodes_sha256": {name: sha(nodes[name].encode()) for name in RUNTIME_NAMES},
        "figures_sha256": {name: sha(png) for name, png in zip(["confusion_matrices.png", "validation_comparison.png"], figures)},
        "notebook_modified": False, "training_rerun": False, "test_metrics_recomputed": False,
        "gradio_version_origin": "deployment_pin; original_notebook_only_specifies_gradio_6",
    })
    json_new("deployment_status.json", {"github_url": "", "demo_url": "", "github_publication_verified": False,
                                      "space_deployment_verified": False, "external_prediction_verified": False})
    for name, before in protected.items():
        if sha((original.parent / name).read_bytes()) != before:
            raise RuntimeError("기존 원본 파일이 변경됐습니다: " + name)
    print(json.dumps({"folder": str(ROOT), "notebook_copy_byte_identical": True,
                      "original_files_unchanged": True, "source_run": runs[-1], "original_code_cells": len(code_counts),
                      "existing_output_figures_copied": len(figures), "model_files_created": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
