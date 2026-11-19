// Gradio의 큐·후속 질문 상태를 같은 컨테이너 프로세스로 전달한다.
export const APP_PORT = 7860;
export const INSTANCE_NAME = "investment-qa";
export const IDLE_TIMEOUT_MS = 5 * 60 * 1000;
export const INSTANCE_RESOURCES = Object.freeze({
  vcpu: 0.25,
  memoryMib: 1024,
  diskMb: 4000,
});

export function routeToInstance(request, env) {
  return env.INVESTMENT_QA.getByName(INSTANCE_NAME).fetch(request);
}

export async function startAndProbe(container, publicOrigin, options = {}) {
  const attempts = options.attempts ?? 40;
  const wait = options.wait ?? ((ms) => new Promise((resolve) => setTimeout(resolve, ms)));
  if (!container.running) {
    container.start({
      image: container.images.app,
      instance: INSTANCE_RESOURCES,
      enableInternet: false,
      env: {
        PORT: String(APP_PORT),
        BUFFETT_MODEL_DIR: "/app/models",
        GRADIO_ANALYTICS_ENABLED: "False",
        GRADIO_ROOT_PATH: publicOrigin,
      },
    });
  }
  await container.setInactivityTimeout(IDLE_TIMEOUT_MS);
  const port = container.getTcpPort(APP_PORT);
  // running 상태와 Gradio의 HTTP 수신 준비 완료를 구분한다.
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await port.fetch("http://container/", {
        signal: AbortSignal.timeout(1000),
      });
      await response.body?.cancel();
      if (response.ok) return;
    } catch {
      // 부팅 중의 접속 실패만 재시도하며 사용자 질문은 재전송하지 않는다.
    }
    if (attempt + 1 < attempts) await wait(500);
  }
  throw new Error("Gradio did not become ready on port 7860");
}

export function proxyRequest(container, request) {
  const original = new URL(request.url);
  const destination = new URL(request.url);
  destination.protocol = "http:";
  destination.host = "container";
  destination.port = "";
  const forwarded = new Request(destination, request);
  forwarded.headers.delete("host");
  forwarded.headers.set("X-Forwarded-Host", original.host);
  forwarded.headers.set("X-Forwarded-Proto", original.protocol.slice(0, -1));
  // 본문과 SSE 응답을 버퍼링하지 않고 그대로 전달한다.
  return container.getTcpPort(APP_PORT).fetch(forwarded);
}
