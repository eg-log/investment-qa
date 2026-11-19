# 검토 자료 목록

| 자료 | 확인할 내용 |
|---|---|
| [프로젝트 포트폴리오](../README.md) | 문제 정의·데이터·전처리·모델·평가·서비스·Lessons Learned |
| [실행 노트북](../project.ipynb) | 전체 학습 코드와 저장된 Colab 출력 |
| [데이터 설명](../data/README.md) | 원본 출처·규모·이용 범위·근거 구조 |
| [모델 산출물](../models/README.md) | 모델·검색기·근거·학습 로그·시험 지표 파일 |
| [평가 분석](EVALUATION.md) | 지표 정의·검증 선택·클래스별 성능·오류 해석 |
| [실행 및 배포 구성](DEPLOYMENT.md) | CPU 실행 환경·경로·서비스 진입점·플랫폼 설정 |
| [Cloudflare 배포](CLOUDFLARE.md) | Docker·Workers 구성·계정 설정·배포 검증 |
| [검증 범위](VALIDATION.md) | 파일 검사·Colab 실행·공개 서비스 검증의 구분 |
| [검토 순서](CLI_HANDOFF.txt) | 코드와 실험 결과를 연결하는 검토 순서 |
| [모델 파일 검사](model_import_check.json) | 최신 실행과 저장 산출물의 해시·로그 일치 결과 |
| [패키지 검사](package_check.json) | 구문·파일·의존성 검사 결과 |

모델의 학습 기록과 독립 평가 점수는 원시 JSON·CSV에 수록하였다. 문서의 표는 해당 기록을 반올림하여 표시한 값이다. 공개 서비스 배포 여부와 Colab 실행 여부는 구분하여 기록한다.
