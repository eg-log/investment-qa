"""Colab 학습 실행의 모델, 근거 데이터, 평가 보고서를 ZIP으로 보관한다."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

EXPECTED_RUN = "runs/20261119_115608_098551"


def export_models(model_dir, output_dir, download=False):
    model_dir = Path(model_dir).expanduser().resolve()
    if model_dir.parent.name != EXPECTED_RUN.split("/")[-1]:
        raise ValueError("이번 최종 실행의 모델 경로를 지정합니다: " + EXPECTED_RUN + "/models")
    manifest_path = model_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("현재 Colab 런타임에 최종 실행의 모델이 없습니다. 보관한 가중치 파일부터 확인합니다.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("training_complete") is not True:
        raise ValueError("학습 완료된 파일이 아닙니다.")
    for name, expected in manifest["artifact_sha256"].items():
        path = model_dir / name
        if Path(name).name != name or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("학습 파일 누락 또는 해시 변경: " + name)
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / ("buffett_models_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".zip")
    report_dir = model_dir.parent / "reports"
    with ZipFile(destination, "x", compression=ZIP_DEFLATED) as archive:
        archive.writestr("active_run.json", json.dumps({"run_dir": EXPECTED_RUN, "model_dir": EXPECTED_RUN + "/models",
                            "report_dir": EXPECTED_RUN + "/reports", "selected_model": manifest["selected_model"]}, ensure_ascii=False, indent=2))
        for name in ["manifest.json", *manifest["artifact_sha256"]]:
            archive.write(model_dir / name, EXPECTED_RUN + "/models/" + name)
        for name in ("confusion_matrices.png", "validation_comparison.png", "error_cases.json", "evidence_results.json", "service_smoke.json"):
            if (report_dir / name).is_file():
                archive.write(report_dir / name, EXPECTED_RUN + "/reports/" + name)
    print("학습 결과 ZIP:", destination)
    if download:
        from google.colab import files
        files.download(str(destination))
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", default="/content/" + EXPECTED_RUN + "/models")
    parser.add_argument("--output-dir", default="/content/exports")
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    export_models(args.model_dir, args.output_dir, args.download)
