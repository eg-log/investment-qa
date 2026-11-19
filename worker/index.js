import { DurableObject } from "cloudflare:workers";
import {
  IDLE_TIMEOUT_MS,
  proxyRequest,
  routeToInstance,
  startAndProbe,
} from "./proxy.js";

export class InvestmentQaContainer extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.ready = false;
    this.starting = undefined;
    this.monitoring = undefined;
    if (ctx.container?.running) {
      ctx.blockConcurrencyWhile(() =>
        ctx.container.setInactivityTimeout(IDLE_TIMEOUT_MS),
      );
      this.observeExit();
    }
  }

  observeExit() {
    if (this.monitoring) return;
    this.monitoring = this.ctx.container.monitor()
      .catch((error) => console.error("Model container exited:", error))
      .finally(() => {
        this.ready = false;
        this.monitoring = undefined;
      });
    this.ctx.waitUntil(this.monitoring);
  }

  async fetch(request) {
    try {
      const container = this.ctx.container;
      if (!container) throw new Error("Container binding is unavailable");
      if (!container.running) this.ready = false;
      if (!this.ready) {
        this.starting ??= startAndProbe(container, new URL(request.url).origin)
          .then(() => {
            this.ready = true;
            this.observeExit();
          })
          .finally(() => { this.starting = undefined; });
        await this.starting;
      }
      return await proxyRequest(container, request);
    } catch (error) {
      this.ready = false;
      console.error("Model service unavailable:", error);
      return Response.json(
        { error: "MODEL_SERVICE_UNAVAILABLE", message: "모델 서비스를 시작하거나 연결하지 못했습니다. 잠시 후 다시 시도해 주세요." },
        { status: 503, headers: { "Retry-After": "10", "Cache-Control": "no-store" } },
      );
    }
  }
}

export default {
  fetch: routeToInstance,
};
