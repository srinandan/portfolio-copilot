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

  constructor(baseUrl = '') {
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
}

export const gatewayService = new GatewayService();
