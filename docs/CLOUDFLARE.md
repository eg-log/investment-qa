# Cloudflare Containers 배포

## 1. 서비스 구조

Cloudflare Worker가 모든 HTTP 경로를 하나의 Durable Object 이름으로 전달하고, Durable Object가 Python 컨테이너를 시작한다. 컨테이너에서는 기존 `build_app()`과 Gradio 인터페이스를 실행한다. 질문 분류·근거 검색·대화 처리·모델 선정 기준은 기존 구현을 사용한다.

```text
브라우저 → workers.dev의 Worker → Durable Object → Python 컨테이너:7860
                                                    └─ 저장 분류기·검색기·근거 데이터
```

`serve_container.py`는 `0.0.0.0:7860`을 사용한다. 공개 요청의 origin은 `GRADIO_ROOT_PATH`로 전달하여 Gradio API와 정적 자원의 기준 주소를 맞춘다. 큐와 SSE 응답은 버퍼링하지 않으며, 실패한 질문 POST를 자동 재전송하지 않는다.

컨테이너 시작 시 가중치·로그·해시를 검사한다. 이미지 빌드에는 실제 Logistic Regression 체크포인트 로드 검사도 포함한다. 원본 SEC ZIP·학습 노트북·질문 데이터 생성 코드는 이미지 빌드 대상에서 제외하며, 배포 과정에 전처리나 학습 명령이 없다.

## 2. 파일 구성

| 파일 | 역할 |
|---|---|
| `Dockerfile` | Python 3.13 의존성 설치, 저장 모델 검사, Gradio 실행 |
| `.dockerignore` | 실행 파일·모델 산출물만 빌드 컨텍스트에 포함 |
| `serve_container.py` | 기존 Gradio 앱의 컨테이너 진입점 |
| `worker/index.js` | 컨테이너 수명·준비 상태·오류 응답 관리 |
| `worker/proxy.js` | 고정 인스턴스 라우팅, HTTP 준비 검사, 스트리밍 전달 |
| `wrangler.jsonc` | 이미지 빌드·Durable Object·workers.dev 설정 |
| `package.json` | Wrangler 및 검사·배포 명령 |
| `.github/workflows/cloudflare.yml` | GitHub Actions 수동 배포 |
| `scripts/check_service.py` | 실행 중인 서비스의 실제 API 질의응답 검사 |

현재 공식 권장인 `durable_object` 스케줄링 정책과 `ctx.container` API를 사용한다. 이 정책은 `max_instances` 설정을 지원하지 않으므로 해당 필드를 사용하지 않는다. 대신 외부 요청으로 인스턴스 이름을 생성하지 않고 코드에서 한 이름으로 고정한다.

리소스는 0.25 vCPU·1,024MiB 메모리·4,000MB 디스크로 설정하였다. 실제 메모리 사용량은 아직 측정하지 않았다. 유휴 유지 시간은 5분이며 유휴 중지·재배포 시 메모리의 대화 상태는 초기화된다. 저장 가중치는 이미지에 포함되어 다음 시작 시 다시 로드된다.

## 3. 사전 조건과 비용

- Node.js 22 이상. 제공된 CI는 Node.js 24를 사용한다.
- Linux 컨테이너를 실행할 수 있는 Docker. 로컬 CLI 배포 시 Docker 엔진이 실행되어 있어야 한다.
- Cloudflare 계정 인증, workers.dev 하위 도메인 및 Containers 사용 권한.
- Workers Paid 플랜. 현재 공식 요금은 월 기본 **5달러**이며, 포함 사용량을 초과한 컨테이너·Workers·Durable Objects 사용량은 추가 과금될 수 있다.

계정 가입·로그인·유료 플랜 활성화·결제는 계정 소유자가 별도로 수행하는 절차이다. 이 구성 파일을 작성하는 과정에서 해당 작업이나 실제 유료 배포는 실행하지 않았다. [공식 요금](https://developers.cloudflare.com/containers/platform/pricing/)

## 4. Docker 로컬 실행

저장소 루트에서 실행한다.

```powershell
docker info
docker build --platform linux/amd64 -t investment-qa .
docker run --rm --name investment-qa-local -p 127.0.0.1:7860:7860 investment-qa
```

브라우저 접속 주소는 `http://127.0.0.1:7860`이다. 별도 터미널에서 실제 HTTP API를 검사한다.

```powershell
docker exec investment-qa-local python scripts/check_service.py http://127.0.0.1:7860
```

검사 대상은 원칙 질문, 애플 1분기 보유량, 2분기 후속 질문, 컨스텔레이션 보유 변화, 확인 불가 질문, 빈 입력이다. 실제 API가 응답한 경우에만 성공 결과가 출력된다. Docker 엔진 부재·이미지 빌드 실패·모델 로드 실패는 실행 성공으로 간주하지 않는다.

## 5. Workers 로컬 개발과 CLI 배포

```powershell
npm install
npm run check
npm test
npm run dev
```

Wrangler 로컬 개발은 Docker 엔진이 필요하다. 최초 `npm install`로 생성되는 `package-lock.json`은 GitHub에 함께 보관한다. 현재 작성 환경은 npm 저장소에 접속할 수 없어 잠금 파일을 생성하지 못했으며, 존재하지 않는 버전이나 잠금 파일을 임의 작성하지 않았다. 설치 이후 재현 설치에는 `npm ci`를 사용할 수 있다.

계정 소유자가 유료 플랜과 배포 권한을 확인한 뒤 인증·배포를 실행한다.

```powershell
npm run login
npm run whoami
npm run deploy
```

`wrangler deploy`가 Worker를 업로드하고 Docker 이미지를 빌드·전송한다. 최종 접속 주소는 **실제 배포 출력의 workers.dev 주소**를 사용한다. 최초 컨테이너 준비에는 추가 시간이 걸릴 수 있다.

```powershell
npx wrangler containers list
npm run logs
```

페이지와 질문 응답이 확인된 이후 실제 주소를 README와 submission.json의 `demo_url`에 기록한다. 현재 해당 주소는 미확정이다.

## 6. GitHub 저장소 연동

공개 소스 저장소는 [eg-log/investment-qa](https://github.com/eg-log/investment-qa)이다. 배포 파일을 같은 저장소 루트에 반영한다. `.github/workflows/cloudflare.yml`은 **workflow_dispatch만 사용하므로 파일 업로드나 push만으로 배포하지 않는다.**

GitHub의 `cloudflare-production` Environment에 `CLOUDFLARE_API_TOKEN`과 `CLOUDFLARE_ACCOUNT_ID`를 Secrets로 설정한다. 토큰은 대상 계정의 Workers·Containers 배포에 필요한 범위로 제한하며 소스코드에 입력하지 않는다. [Cloudflare 공식 CI 인증 안내](https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/)

계정 설정과 비용 확인을 마친 뒤 Actions의 `Deploy Cloudflare Containers`에서 Run workflow를 실행한다. 워크플로는 프록시 검사, Docker 확인, 이미지·Worker 배포를 수행한다. 필요하면 Environment의 승인 정책으로 운영 배포를 제한할 수 있다.

## 7. 배포 후 확인

실제 workers.dev 주소를 브라우저로 열어 원칙 답변·출처·후속 질문·입력 오류·초기화를 확인한다. Python 의존성이 준비된 환경에서는 `python scripts/check_service.py` 뒤에 실제 주소를 지정하여 API 검사를 수행할 수 있다.

검증된 공개 주소와 실제 화면 3장을 포트폴리오에 반영한다. Worker 프록시 단위 검사는 Cloudflare 원격 실행이나 모델의 실제 HTTP 추론 검사를 대신하지 않는다. 현재 실행·미실행 항목은 [Cloudflare 검사 기록](cloudflare_check.json)에 구분되어 있다.

공식 참고: [Containers 시작 안내](https://developers.cloudflare.com/containers/get-started/), [Wrangler 설정](https://developers.cloudflare.com/containers/configuration/wrangler/), [Durable Object API](https://developers.cloudflare.com/containers/api/durable-object-container/), [스케줄링 정책](https://developers.cloudflare.com/containers/configuration/scheduling-policy/).
