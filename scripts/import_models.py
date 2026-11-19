"""실험 로그와 파일 해시를 대조하여 저장된 모델 ZIP을 등록한다."""
import argparse
import json
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from model_assets import MODEL_FILES, digest, read_json, validate_model_bytes

ROOT = Path(__file__).resolve().parents[1]


def import_archive(archive_path):
    source = read_json(ROOT / "source_manifest.json")
    with ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("ZIP 안에 중복 경로가 있습니다.")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
                raise ValueError("ZIP 내부 상대경로를 확인합니다.")
        if "active_run.json" in names:
            active = json.loads(archive.read("active_run.json"))
            if active.get("run_dir") != source["source_run"]:
                raise ValueError("이번 최종 실행 " + source["source_run"] + "의 ZIP이 아닙니다. 확인된 ZIP: " + str(active.get("run_dir")))
        candidates = [name for name in names if PurePosixPath(name).name == "manifest.json"]
        if len(candidates) != 1:
            raise ValueError("학습 manifest.json이 한 개 포함된 결과 ZIP을 지정합니다.")
        prefix = candidates[0][:-len("manifest.json")]
        manifest = json.loads(archive.read(candidates[0]))
        file_names = MODEL_FILES | set(manifest.get("artifact_sha256", {}))
        if any(Path(name).name != name for name in file_names):
            raise ValueError("manifest의 파일 경로를 확인합니다.")
        blobs = {name: archive.read(prefix + name) for name in file_names}
        validate_model_bytes(blobs, source)
        planned = {ROOT / "models" / name: blob for name, blob in blobs.items()}
        report_prefix = prefix[:-len("models/")] + "reports/" if prefix.endswith("models/") else "reports/"
        for name in ("error_cases.json", "evidence_results.json", "service_smoke.json"):
            key = report_prefix + name
            if key in names:
                planned[ROOT / "reports" / name] = archive.read(key)
        for path, blob in planned.items():
            if path.exists() and path.read_bytes() != blob:
                raise FileExistsError("기존 파일을 보존합니다. 다른 파일을 덮어쓰지 않습니다: " + str(path))
        for path, blob in planned.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blob)
    print(json.dumps({"source_run": source["source_run"], "archive_sha256": digest(archive_path),
                      "files_copied": len(planned), "retrained": False, "metrics_recomputed": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    try:
        import_archive(args.archive.expanduser().resolve())
    except (OSError, ValueError, KeyError, BadZipFile) as error:
        parser.exit(1, str(error) + "\n")
