import type {
  HealthStatus,
  AuthCheckResult,
  HoldingsSnapshot,
  DocumentItem,
  ProposedAction,
  SpendingReport,
  DriftReport
} from '../types';

export class ApiService {
  private baseUrl: string;

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

  async streamPlan(
    req: { user_id: string; message: string; session_id?: string },
    onEvent: (event: Record<string, any>) => void,
    onError?: (err: any) => void
  ): Promise<void> {
    const res = await this.triggerPlan(req);
    await readSSEStream(res, onEvent, onError);
  }

  async streamPlanResume(
    req: {
      user_id: string;
      session_id: string;
      invocation_id: string;
      interrupt_id: string;
      payload: Record<string, unknown>;
    },
    onEvent: (event: Record<string, any>) => void,
    onError?: (err: any) => void
  ): Promise<void> {
    const res = await this.resumePlan(req);
    await readSSEStream(res, onEvent, onError);
  }
}

export async function readSSEStream(
  response: Response,
  onEvent: (event: Record<string, any>) => void,
  onError?: (err: any) => void
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('data:')) {
          const jsonStr = trimmed.slice(5).trim();
          if (jsonStr) {
            try {
              const data = JSON.parse(jsonStr);
              onEvent(data);
            } catch {
              onEvent({ raw: jsonStr });
            }
          }
        }
      }
    }
    if (buffer.trim().startsWith('data:')) {
      const jsonStr = buffer.trim().slice(5).trim();
      if (jsonStr) {
        try {
          const data = JSON.parse(jsonStr);
          onEvent(data);
        } catch {
          onEvent({ raw: jsonStr });
        }
      }
    }
  } catch (err) {
    if (onError) onError(err);
    else throw err;
  }
}

export const apiService = new ApiService();
export const gatewayService = apiService;
export { ApiService as GatewayService };
