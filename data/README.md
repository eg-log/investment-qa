# 데이터 구성과 출처

본 프로젝트는 SEC 보유 기록, Berkshire Hathaway 주주서한의 원칙 요약, 한국어 질문 분류 자료를 사용한다. 기관의 신고 사실과 공개 투자 원칙은 별도 근거로 관리한다.

## 1. SEC 보유 기록

공식 출처는 [SEC Form 13F 데이터셋](https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets)이다. 작성자가 다운로드한 2025년 3~5월·6~8월 제출분 ZIP에서 CIK `0001067983`의 Berkshire Hathaway 공시를 추출하였다.

- 보유 기준일: 2025-03-31, 2025-06-30
- 원본 INFOTABLE: 3,440,002행·3,360,306행
- 대상 공시: 원본 공시 2건과 추가 공개 수정 공시 1건
- 추출 행: 228행
- 분기별 증권 보유: 80건
- 분기 비교 대상: 42건

`SUBMISSION`·`COVERPAGE`·`SUMMARYPAGE`·`INFOTABLE`은 공시 고유번호로 연결한다. CUSIP과 CIK는 문자열로 보관하며 주식/원금과 PUT/CALL 등 증권 유형을 구분한다. VALUE의 단위는 해당 원본 메타데이터에서 확인한 USD이다.

## 2. 투자 원칙

[principles.json](principles.json)은 [공식 주주서한](https://www.berkshirehathaway.com/letters/letters.html)에 연결된 한국어 원칙 요약 14개이다. 원칙 ID, 판단 기준, 적용 조건, 보고연도, 발행연도, 출처 URL, 문서 내 위치, 검수 상태를 포함한다.

요약은 원문 인용문이 아니라 AI 보조로 작성한 의역 초안이며 독립 수동 검수는 미완료이다. 원문 전체는 포함하지 않는다. 원문에 명시된 이용 조건과 저작권은 해당 문서에 적용되며 별도 오픈 라이선스가 확인된 것으로 표시하지 않는다.

## 3. 서비스 근거

[models/knowledge.json](../models/knowledge.json)에 근거 139건을 수록하였다.

| 유형 | 건수 | 의미 |
|---|---:|---|
| INVESTMENT_PRINCIPLE | 14 | 공개 투자 원칙의 한국어 요약 |
| HOLDING_FACT | 82 | 증권 보유 80건과 보고 기간별 공시 근거 2건 |
| HOLDING_CHANGE | 42 | 두 분기 보유 수량 비교 |
| UNSUPPORTED | 1 | 13F가 입증하지 않는 정보의 범위 |

각 항목은 `evidence_id`, `kind`, `text`, `search_text`, `evidence_type`, `source_urls`, `payload`로 구성된다. 근거 유형은 STATED 14건·CALCULATED 122건·OBSERVED 2건·UNKNOWN 1건이다. 일반 원칙을 특정 종목의 거래 동기에 자동 연결하지 않는다.

## 4. 질문 자료와 분할

질문 예시는 sample_id·question·target_label·group_id·evidence_ids·source_id·evidence_type·review_status를 포함한다. 총 96개 중 train 57개·validation 15개·test 12개·development 12개로 분리하였다. 분할 시드는 42이다.

분할 자료는 [train.json](dataset/train.json), [validation.json](dataset/validation.json), [test.json](dataset/test.json), [development.json](dataset/development.json)에 수록하였다. 네 분할을 담은 사전을 `json.dumps(splits, ensure_ascii=False, sort_keys=True)`로 직렬화한 SHA256은 `99e8f21df00046aee6e4f4a1abae083c45064d959d203834db3bee4e6beb1bd3`으로 최종 체크포인트의 `split_sha256`과 일치한다.

동일 의미군·증권 그룹·질문 ID·정규화 질문의 분할 간 중복 검사 결과는 노트북에 수록하였다. 모델별 성능과 클래스 분포는 저장소 README 및 [평가 문서](../docs/EVALUATION.md)에 제시하였다.

## 5. 이용 범위

대용량 SEC 원본 ZIP과 주주서한 원문 전체는 저장소에 포함하지 않는다. 전체 정형화·질문 생성·분할 코드는 [project.ipynb](../project.ipynb)에 수록되어 있으며, 저장된 근거 데이터만으로 서비스 추론이 가능하다. 개별 거래의 실제 동기, 버핏 개인 계좌, 미래 주가는 이 자료의 입증 범위에 포함되지 않는다.
