# 실행 및 배포 구성

## 서비스 실행

본 시스템은 저장된 질문 분류기·검색기·근거 파일을 로드하여 실행한다. 분류와 대화 처리는 기존 `app.py`·`persona_runtime.py`를 사용하며, Cloudflare 컨테이너에서는 `serve_container.py`가 같은 앱을 0.0.0.0:7860에서 시작한다.

Python 의존성과 모델 경로는 `requirements.txt`, `models/manifest.json`, `source_manifest.json`으로 관리한다. 모델이 없거나 해시·학습 로그가 일치하지 않으면 오류를 반환한다. 실행에 SEC 원본 자료의 재처리나 모델 재학습은 포함하지 않는다.

## 로컬 Python 실행

```bash
python -m pip install -r requirements.txt
python scripts/check_package.py
python scripts/smoke_test.py
python app.py
```

기본 접속 주소는 http://127.0.0.1:7860이다. 학습 환경은 Python 3.13.18, scikit-learn 1.6.1, NumPy 2.4.6, pandas 2.2.3, joblib 1.6.0이다. 서비스 Gradio 버전은 6.32.0으로 고정하였다.

## Docker 및 Cloudflare

```bash
docker build --platform linux/amd64 -t investment-qa .
docker run --rm --name investment-qa-local -p 127.0.0.1:7860:7860 investment-qa
```

별도 터미널의 HTTP 검사 명령:

```bash
docker exec investment-qa-local python scripts/check_service.py http://127.0.0.1:7860
```

Cloudflare Worker와 Durable Object가 컨테이너를 시작하고 모든 Gradio 경로를 같은 인스턴스에 전달한다. 최종 서비스 주소는 실제 배포 결과의 workers.dev 주소이며 현재 미확정이다. 계정 소유자의 인증과 Workers Paid 플랜이 필요하다. 실제 Docker 및 원격 배포 검증은 아직 실행하지 않았다.

설정 파일, CLI 배포, 비용, GitHub Actions 연동 및 배포 후 검증 절차는 [CLOUDFLARE.md](CLOUDFLARE.md)에 수록하였다. 실험·검증 범위는 [VALIDATION.md](VALIDATION.md)에서 확인할 수 있다.
