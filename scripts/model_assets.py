"""저장된 모델과 실험 메타데이터의 일치 여부를 검사한다."""
import hashlib
import json
from pathlib import Path

MODEL_NAMES = {"word_tfidf_logreg", "char_tfidf_svm"}
MODEL_FILES = {"manifest.json", "selection.json", "training_log.json", "test_results.json", "comparison.csv",
               "knowledge.json", "retriever.joblib", "word_tfidf_logreg.joblib", "char_tfidf_svm.joblib"}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_model_bytes(blobs, source):
    missing = MODEL_FILES - set(blobs)
    if missing:
        raise FileNotFoundError("최종 실행의 저장 파일이 없습니다: " + ", ".join(sorted(missing)))
    manifest = json.loads(blobs["manifest.json"])
    if manifest.get("training_complete") is not True or set(manifest.get("models", [])) != MODEL_NAMES:
        raise ValueError("학습 완료된 기존 두 모델의 파일이 아닙니다.")
    selection = json.loads(blobs["selection.json"])
    if selection != source["selection"] or manifest.get("selection") != selection or manifest.get("selected_model") != selection["selected_model"]:
        raise ValueError("원본 노트북의 모델 선정 결과와 다릅니다.")
    if json.loads(blobs["training_log.json"]) != source["training_log_from_original_output"]:
        raise ValueError("최종 실행 " + source["source_run"] + "의 학습 로그와 다릅니다. 이전 실행 모델로 대체하지 않습니다.")
    for field, package in [("sklearn_version", "scikit-learn"), ("numpy_version", "numpy"),
                           ("pandas_version", "pandas"), ("joblib_version", "joblib")]:
        if manifest.get(field) != source["source_versions"][package]:
            raise ValueError("기존 학습 환경과 다릅니다: " + package)
    hashes = manifest.get("artifact_sha256", {})
    if not (MODEL_FILES - {"manifest.json"}).issubset(hashes):
        raise ValueError("manifest에 필수 파일의 해시가 없습니다.")
    for name, expected in hashes.items():
        if Path(name).name != name or name not in blobs or hashlib.sha256(blobs[name]).hexdigest() != expected:
            raise ValueError("학습 파일의 해시가 다르거나 파일이 없습니다: " + name)
    results = json.loads(blobs["test_results.json"])
    for model, values in source["test_metrics_from_original_display"].items():
        for metric, value in values.items():
            if abs(results[model][metric] - value) > 0.000001:
                raise ValueError("기존 시험 출력과 다른 값입니다: " + model + "/" + metric)
    return manifest


def validate_model_folder(folder, source_path):
    folder = Path(folder)
    missing = sorted(name for name in MODEL_FILES if not (folder / name).is_file())
    if missing:
        raise FileNotFoundError("저장된 최종 모델이 필요합니다. scripts/import_models.py로 최신 모델 ZIP을 등록합니다. 누락: " + ", ".join(missing))
    manifest = read_json(folder / "manifest.json")
    names = MODEL_FILES | set(manifest.get("artifact_sha256", {}))
    if any(Path(name).name != name for name in names):
        raise ValueError("모델 파일의 상대경로를 확인합니다.")
    return validate_model_bytes({name: (folder / name).read_bytes() for name in names}, read_json(source_path))
