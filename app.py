"""저장된 질문 분류기와 근거 데이터로 Gradio 질의응답 서비스를 실행한다."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build_app():
    from scripts.model_assets import validate_model_folder
    configured = os.environ.get("BUFFETT_MODEL_DIR", "models")
    model_dir = Path(configured).expanduser()
    if not model_dir.is_absolute():
        model_dir = ROOT / model_dir
    validate_model_folder(model_dir, ROOT / "source_manifest.json")
    # 저장 모델 검증 후 질의응답 인터페이스를 구성한다.
    from persona_runtime import create_gradio
    return create_gradio(model_dir)


if __name__ == "__main__":
    build_app().launch(
        server_name="0.0.0.0" if os.environ.get("SPACE_ID") else "127.0.0.1",
        server_port=int(os.environ.get("PORT", "7860")),
        share=False,
        show_error=False,
    )
