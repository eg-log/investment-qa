"""저장 모델과 기존 Gradio 화면을 컨테이너의 외부 수신 포트에서 실행한다."""
import os

from app import build_app


def main():
    build_app().launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", "7860")),
        root_path=os.environ.get("GRADIO_ROOT_PATH", ""),
        share=False,
        show_error=False,
    )


if __name__ == "__main__":
    main()
