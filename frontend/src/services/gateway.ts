import type {
  HealthStatus,
  AuthCheckResult,
  HoldingsSnapshot,
  DocumentItem,
  ProposedAction,
  SpendingReport,
  DriftReport
} from '../types';

export class GatewayService {
  private baseUrl: string;

  // In production the SPA is served by the frontend Go container
  // (frontend/server/main.go), which reverse-proxies /api and /health to the
  // gateway with a Google-signed ID token. Fetches must be relative so the
  // browser stays on the frontend origin — otherwise the request goes
  // straight to the gateway from the browser with no token attached, and
  // Cloud Run returns 401. In Vite dev, the same relative fetch is caught
  // by the dev proxy in vite.config.ts. Baking a hard-coded gateway URL into
  // the JS bundle at build time (the previous VITE_GATEWAY_URL path) is what
  // was making the browser call localhost:8080 directly on Cloud Run — it
  // must not come back. Tests pass an explicit baseUrl.
  constructor(baseUrl: string = '') {
    this.baseUrl = baseUrl;
  }

  async checkHealth(): Promise<HealthStatus> {
    const res = await fetch(`${this.baseUrl}/health`);
    if (!res.ok) {
      throw new Error(`Health check failed with status ${res.status}`);
    }
    return res.json();
  }

  async checkAuth(): Promise<AuthCheckResult> {
    const res = await fetch(`${this.baseUrl}/api/auth-check`);
    if (!res.ok) {
      throw new Error(`Auth check failed with status ${res.status}`);
    }
    return res.json();
  }

  connectStream(
    onMessage: (data: Record<string, unknown>) => void,
    onClose?: () => void,
    onError?: (err: Event) => void
  ): EventSource {
    const source = new EventSource(`${this.baseUrl}/api/stream`);

    source.addEventListener('message', (event) => {
      try {
        const parsed = JSON.parse(event.data);
        onMessage(parsed);
      } catch {
        onMessage({ message: event.data });
      }
    });

    source.addEventListener('close', () => {
      source.close();
      onClose?.();
    });

    source.onerror = (err) => {
      onError?.(err);
    };

    return source;
  }

  async getHoldings(): Promise<HoldingsSnapshot> {
    const res = await fetch(`${this.baseUrl}/api/holdings`);
    if (!res.ok) {
      throw new Error(`Get holdings failed with status ${res.status}`);
    }
    return res.json();
  }

  async getDocuments(): Promise<DocumentItem[]> {
    const res = await fetch(`${this.baseUrl}/api/documents`);
    if (!res.ok) {
      throw new Error(`Get documents failed with status ${res.status}`);
    }
    return res.json();
  }

  async getSpendingReport(windowMonths = 3): Promise<SpendingReport> {
    const res = await fetch(`${this.baseUrl}/api/spending_report?window_months=${windowMonths}`);
    if (!res.ok) {
      throw new Error(`Get spending report failed with status ${res.status}`);
    }
    return res.json();
  }

  async getDriftReport(): Promise<DriftReport> {
    const res = await fetch(`${this.baseUrl}/api/drift_report`);
    if (!res.ok) {
      throw new Error(`Get drift report failed with status ${res.status}`);
    }
    return res.json();
  }

  async approveAction(actionId: string): Promise<ProposedAction> {
    const res = await fetch(`${this.baseUrl}/api/proposed_actions/${encodeURIComponent(actionId)}/approve`, {
      method: 'POST'
    });
    if (!res.ok) {
      throw new Error(`Approve action failed with status ${res.status}`);
    }
    return res.json();
  }

  async rejectAction(actionId: string): Promise<ProposedAction> {
    const res = await fetch(`${this.baseUrl}/api/proposed_actions/${encodeURIComponent(actionId)}/reject`, {
      method: 'POST'
    });
    if (!res.ok) {
      throw new Error(`Reject action failed with status ${res.status}`);
    }
    return res.json();
  }

  async triggerPlan(req: { user_id: string; message: string; session_id?: string }): Promise<Response> {
    const res = await fetch(`${this.baseUrl}/api/plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req)
    });
    if (!res.ok) {
      throw new Error(`Trigger plan failed with status ${res.status}`);
    }
    return res;
  }

  async resumePlan(req: {
    user_id: string;
    session_id: string;
    invocation_id: string;
    interrupt_id: string;
    payload: Record<string, unknown>;
  }): Promise<Response> {
    const res = await fetch(`${this.baseUrl}/api/plan/resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req)
    });
    if (!res.ok) {
      throw new Error(`Resume plan failed with status ${res.status}`);
    }
    return res;
  }
}

export const gatewayService = new GatewayService();
