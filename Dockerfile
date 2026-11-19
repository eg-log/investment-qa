FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    BUFFETT_MODEL_DIR=/app/models \
    GRADIO_ANALYTICS_ENABLED=False \
    GRADIO_TEMP_DIR=/tmp/gradio \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

COPY app.py persona_runtime.py serve_container.py source_manifest.json ./
COPY scripts/__init__.py scripts/model_assets.py scripts/check_service.py ./scripts/
COPY models/word_tfidf_logreg.joblib \
     models/char_tfidf_svm.joblib \
     models/retriever.joblib \
     models/knowledge.json \
     models/manifest.json \
     models/selection.json \
     models/training_log.json \
     models/test_results.json \
     models/comparison.csv ./models/

# 파일 검사와 실제 체크포인트 로드에 실패하면 이미지를 완성하지 않는다.
RUN python -c "from scripts.model_assets import validate_model_folder; validate_model_folder('models', 'source_manifest.json'); from persona_runtime import EvidenceChat; model = EvidenceChat('models'); assert model.key == 'word_tfidf_logreg'; print('Checkpoint loaded:', model.key)"

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/', timeout=4).close()"

CMD ["python", "serve_container.py"]
