# 학습 모델과 저장 산출물

실험 `runs/20261119_115608_098551`에서 저장한 질문 분류기 두 개, 검색기, 근거 데이터 및 평가 결과를 수록하였다. 저장 모델은 서비스 시작 시 로드되며 추론을 위한 재학습은 필요하지 않다.

## 파일 구성

| 파일 | 역할 |
|---|---|
| [word_tfidf_logreg.joblib](word_tfidf_logreg.joblib) | 단어 TF-IDF와 Logistic Regression의 학습 파이프라인, 최종 서비스 모델 |
| [char_tfidf_svm.joblib](char_tfidf_svm.joblib) | 문자 TF-IDF와 Linear SVM의 학습 파이프라인, 비교 모델 |
| [retriever.joblib](retriever.joblib) | 공개 근거 검색용 TF-IDF 벡터라이저와 근거 행렬 |
| [knowledge.json](knowledge.json) | 근거 텍스트·유형·출처·수치 payload 139건 |
| [manifest.json](manifest.json) | 학습 완료 여부·환경 버전·파일 해시·선정 결과 |
| [selection.json](selection.json) | 검증 기준 최종 모델 선정과 테스트 미사용 기록 |
| [training_log.json](training_log.json) | 모델별 C 후보의 학습·검증 성능, 최적화 반복 수, 학습 시간 |
| [test_results.json](test_results.json) | 테스트 예측·혼동행렬·클래스별 성능·집계 지표 |
| [comparison.csv](comparison.csv) | 테스트 지표의 모델별 비교표 |

## 선정 기준과 환경

최종 모델은 `word_tfidf_logreg`이다. 검증 Macro-F1, 검증 Accuracy 순서로 비교하며 동률일 때 베이스라인을 선택하였다. 테스트 점수는 모델 선택에 사용하지 않았다.

학습 환경은 Python 3.13.18, scikit-learn 1.6.1, NumPy 2.4.6, pandas 2.2.3, joblib 1.6.0이다. 현재 산출물의 학습 로그는 노트북 실행 출력과 일치하며 manifest에 기록된 8개 파일의 SHA256 검사를 통과하였다.

## 서비스 연동

저장소 루트의 `app.py`는 이 폴더를 기본 모델 경로로 사용한다. `scripts/model_assets.py`에서 학습 완료·선정 결과·실행 로그·파일 해시를 검사하고, `persona_runtime.py`의 `EvidenceChat`이 분류기와 검색기를 로드한다. 다른 실행 경로는 환경변수 `BUFFETT_MODEL_DIR`로 지정할 수 있다.
