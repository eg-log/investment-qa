# 실행 및 배포 구성

## 1. 실행 환경

서비스는 학습한 질문 분류기와 근거 데이터를 CPU에서 사용하는 구성이다. 학습 환경은 Python 3.13.18, scikit-learn 1.6.1, NumPy 2.4.6, pandas 2.2.3, joblib 1.6.0이다. Gradio 6.32.0을 웹 인터페이스용 버전으로 지정하였다.

## 2. 파일 구조

```text
.
├── project.ipynb          # 데이터 처리·학습·평가·Colab 실행 결과
├── app.py                 # 서비스 진입점
├── persona_runtime.py     # 질문 분류 결과에 따른 근거 조회·답변·대화 처리
├── requirements.txt       # 서비스 의존성
├── source_manifest.json   # 노트북·실험·추론 정의의 식별 정보
├── models/                # 학습 모델·검색기·근거 데이터·평가 결과
├── data/                  # 원칙 요약과 데이터 설명
├── reports/               # 혼동행렬·오류 사례·근거 평가·질의응답 기록
├── scripts/               # 산출물 검사·입출력·시연 검증 도구
└── docs/                  # 평가·실행·검증 설명
```

## 3. 저장 가중치 기반 실행

저장소 루트에서 다음 명령을 실행한다.

```bash
python -m pip install -r requirements.txt
python scripts/check_package.py
python scripts/smoke_test.py
python app.py
```

기본 모델 경로는 `models/`, 로컬 접속 주소는 `http://127.0.0.1:7860`이다. `BUFFETT_MODEL_DIR`는 모델 경로를, `PORT`는 서버 포트를 지정한다. Hugging Face 환경변수 `SPACE_ID`가 있는 경우 서버는 `0.0.0.0`에 바인딩한다.

서비스 시작 과정은 산출물 검사 → 분류기·검색기·근거 로드 → Gradio 인터페이스 생성 순서이다. 모델 파일 누락·해시 불일치·학습 환경 불일치 시 오류를 반환한다. 질문 처리 중에는 저장된 모델의 `predict`와 검색기의 `transform`을 사용한다.

## 4. 학습 및 산출물 관리

전체 전처리·질문 데이터 구성·분할·두 모델 학습 코드는 `project.ipynb`에 있다. `train` 모드는 원본 SEC ZIP 두 개를 입력받으며, `inference` 모드는 저장 모델을 로드한다. 서비스 기본 실행에는 재학습이나 원본 SEC 자료의 재처리가 필요하지 않다.

`scripts/export_models_colab.py`는 Colab의 저장 파일을 ZIP으로 보관한다. `scripts/import_models.py`는 실행 로그·선정 결과·환경 버전·파일 해시를 검사한 뒤 ZIP의 산출물을 등록한다. 학습 모델과 기록된 시험 지표를 다시 계산하는 도구는 아니다.

## 5. Hugging Face Spaces 구성

README의 YAML 설정은 `sdk: gradio`, `python_version: 3.13`, `sdk_version: 6.32.0`, `app_file: app.py`이다. CPU Basic을 배포 대상으로 지정하였으며 GPU는 요구하지 않는다. 서비스 실행 파일·검사 모듈·source_manifest.json·모델 폴더는 동일한 저장소 루트 구조를 유지한다.

Space는 저장소 변경 시 의존성을 설치하고 앱을 시작한다. 설정 항목과 실행 방식은 [Hugging Face 공식 문서](https://huggingface.co/docs/hub/spaces-config-reference)를 따른다. 하드웨어 및 Space 생성 권한은 플랫폼의 계정·플랜 조건에 따른다.

현재 Colab에서의 실행 기록과 저장 파일 검사는 확인되었으나, 상시 공개 Space의 URL과 외부 브라우저 추론 검증은 확보되지 않았다. Colab 임시 공유 링크와 상시 공개 배포는 구분한다.

## 6. 검증 자료

- 모델별 학습·검증 로그: `models/training_log.json`
- 독립 테스트 평가: `models/test_results.json`
- 근거 평가: `reports/evidence_results.json`
- Colab 후속 질문 시연: `reports/service_smoke.json`
- 파일 및 코드 검사: `docs/package_check.json`, `docs/model_import_check.json`
- 검증 범위 설명: [VALIDATION.md](VALIDATION.md)
