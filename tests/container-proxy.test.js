import test from "node:test";
import assert from "node:assert/strict";
import {
  APP_PORT,
  INSTANCE_NAME,
  INSTANCE_RESOURCES,
  proxyRequest,
  routeToInstance,
  startAndProbe,
} from "../worker/proxy.js";

test("UI, queue, and asset paths share one named instance", async () => {
  const names = [];
  const env = { INVESTMENT_QA: { getByName(name) {
    names.push(name);
    return { fetch: async () => new Response("upstream") };
  } } };
  for (const path of ["/", "/gradio_api/queue/join", "/gradio_api/queue/data", "/assets/app.js"]) {
    await routeToInstance(new Request("https://example.test" + path), env);
  }
  assert.deepEqual(names, Array(4).fill(INSTANCE_NAME));
});

test("proxy preserves method, body, path, query, and external origin", async () => {
  const body = JSON.stringify({ data: ["question", []], session_hash: "test-session" });
  let observed;
  const container = { getTcpPort(port) {
    assert.equal(port, APP_PORT);
    return { fetch: async (request) => {
      observed = { method: request.method, url: request.url, body: await request.text(), headers: request.headers };
      return new Response("accepted");
    } };
  } };
  await proxyRequest(container, new Request("https://example.test/gradio_api/queue/join?x=1", {
    method: "POST", body, headers: { "Content-Type": "application/json" },
  }));
  assert.equal(observed.method, "POST");
  assert.equal(observed.body, body);
  assert.equal(observed.url, "http://container/gradio_api/queue/join?x=1");
  assert.equal(observed.headers.get("X-Forwarded-Host"), "example.test");
  assert.equal(observed.headers.get("X-Forwarded-Proto"), "https");
});

test("streaming responses are returned without collecting their body", async () => {
  const stream = new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode("data: ready\n\n")); } });
  const upstream = new Response(stream, { headers: { "Content-Type": "text/event-stream" } });
  const container = { getTcpPort: () => ({ fetch: async () => upstream }) };
  const response = await proxyRequest(container, new Request("https://example.test/gradio_api/queue/data"));
  assert.equal(response, upstream);
  const reader = response.body.getReader();
  const first = await reader.read();
  assert.equal(new TextDecoder().decode(first.value), "data: ready\n\n");
  await reader.cancel();
});

test("cold startup requires a successful HTTP probe and disables outbound Internet", async () => {
  let started, probes = 0;
  const container = {
    running: false, images: { app: "test-image" },
    start(options) { started = options; this.running = true; },
    async setInactivityTimeout(ms) { assert.equal(ms, 300000); },
    getTcpPort: () => ({ fetch: async () => {
      probes += 1;
      if (probes === 1) throw new Error("port not ready");
      return new Response("probe", { status: probes === 2 ? 503 : 200 });
    } }),
  };
  await startAndProbe(container, "https://example.test", { wait: async () => {} });
  assert.equal(probes, 3);
  assert.equal(started.image, "test-image");
  assert.equal(started.enableInternet, false);
  assert.deepEqual(started.instance, INSTANCE_RESOURCES);
  assert.equal(started.env.GRADIO_ROOT_PATH, "https://example.test");
});

test("an existing container is probed without starting another process", async () => {
  const container = {
    running: true,
    start() { assert.fail("existing container restarted"); },
    setInactivityTimeout: async () => {},
    getTcpPort: () => ({ fetch: async () => new Response("ready") }),
  };
  await startAndProbe(container, "https://example.test");
});

test("startup failure is reported when HTTP readiness never succeeds", async () => {
  const container = {
    running: true, setInactivityTimeout: async () => {},
    getTcpPort: () => ({ fetch: async () => new Response("unavailable", { status: 503 }) }),
  };
  await assert.rejects(startAndProbe(container, "https://example.test", { attempts: 2, wait: async () => {} }), /did not become ready/);
});

test("failed question POST is not automatically replayed", async () => {
  let calls = 0;
  const container = { getTcpPort: () => ({ fetch: async () => { calls += 1; throw new Error("connection lost"); } }) };
  await assert.rejects(proxyRequest(container, new Request("https://example.test/gradio_api/queue/join", { method: "POST", body: "question" })), /connection lost/);
  assert.equal(calls, 1);
});

test("local Wrangler origin port is not forwarded as the container port", async () => {
  let url;
  const container = { getTcpPort(port) {
    assert.equal(port, 7860);
    return { fetch: async (request) => { url = request.url; return new Response("ready"); } };
  } };
  await proxyRequest(container, new Request("http://localhost:8787/config"));
  assert.equal(url, "http://container/config");
});
