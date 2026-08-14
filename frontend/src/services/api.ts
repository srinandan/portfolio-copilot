import type {
  HealthStatus,
  HoldingsSnapshot,
  DocumentItem,
  SpendingReport,
  DriftReport,
  UserProfile,
  OnboardingProfile
} from '../types';
import { traceRequest } from './tracing';

export class ApiService {
  private baseUrl: string;

  constructor(baseUrl: string = '') {
    this.baseUrl = baseUrl;
  }

  /**
   * fetch wrapper that records a client span and injects a W3C `traceparent`
   * header, so every request continues the browser trace into the Go server and
   * orchestrator. Header-only injection (rather than patching global fetch)
   * keeps the SSE streaming reader untouched. The span ends once response
   * headers arrive; the SSE body then streams outside the span.
   */
  private async tracedFetch(name: string, url: string, init: RequestInit = {}): Promise<Response> {
    const existing = (init.headers as Record<string, string>) || {};
    const { headers, span } = traceRequest(name, existing, {
      'http.url': url,
      'http.method': init.method || 'GET'
    });
    try {
      const res = await fetch(url, { ...init, headers });
      span.setAttribute('http.status_code', res.status);
      return res;
    } catch (err) {
      span.setAttribute('error', true);
      throw err;
    } finally {
      span.end();
    }
  }

  async checkHealth(): Promise<HealthStatus> {
    const res = await this.tracedFetch('GET /health', `${this.baseUrl}/health`);
    if (!res.ok) {
      throw new Error(`Health check failed with status ${res.status}`);
    }
    return res.json();
  }

  async getHoldings(): Promise<HoldingsSnapshot> {
    const res = await this.tracedFetch('GET /api/holdings', `${this.baseUrl}/api/holdings`);
    if (!res.ok) {
      throw new Error(`Get holdings failed with status ${res.status}`);
    }
    return res.json();
  }

  async getDocuments(): Promise<DocumentItem[]> {
    const res = await this.tracedFetch('GET /api/documents', `${this.baseUrl}/api/documents`);
    if (!res.ok) {
      throw new Error(`Get documents failed with status ${res.status}`);
    }
    return res.json();
  }

  async uploadDocument(
    file: File,
    documentType: string,
    targetTable?: string,
    userId = 'demo_user'
  ): Promise<DocumentItem> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);
    formData.append('user_id', userId);
    if (targetTable) {
      formData.append('target_table', targetTable);
    }

    const res = await this.tracedFetch('POST /api/documents', `${this.baseUrl}/api/documents`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.error || `Upload document failed with status ${res.status}`);
    }
    return res.json();
  }

  async getOnboarding(userId = 'demo_user'): Promise<OnboardingProfile> {
    const res = await this.tracedFetch(
      'GET /api/onboarding',
      `${this.baseUrl}/api/onboarding?user_id=${encodeURIComponent(userId)}`
    );
    if (!res.ok) {
      throw new Error(`Get onboarding profile failed with status ${res.status}`);
    }
    return res.json();
  }

  async getSpendingReport(windowMonths = 3): Promise<SpendingReport> {
    const res = await this.tracedFetch(
      'GET /api/spending_report',
      `${this.baseUrl}/api/spending_report?window_months=${windowMonths}`
    );
    if (!res.ok) {
      throw new Error(`Get spending report failed with status ${res.status}`);
    }
    return res.json();
  }

  async getDriftReport(): Promise<DriftReport> {
    const res = await this.tracedFetch('GET /api/drift_report', `${this.baseUrl}/api/drift_report`);
    if (!res.ok) {
      throw new Error(`Get drift report failed with status ${res.status}`);
    }
    return res.json();
  }

  async getUserProfile(userId = 'demo_user'): Promise<UserProfile> {
    const res = await this.tracedFetch(
      'GET /api/profile',
      `${this.baseUrl}/api/profile?user_id=${encodeURIComponent(userId)}`
    );
    if (!res.ok) {
      throw new Error(`Get user profile failed with status ${res.status}`);
    }
    return res.json();
  }

  async updateUserProfile(profile: UserProfile): Promise<{ status: string; profile: UserProfile }> {
    const res = await this.tracedFetch('POST /api/profile', `${this.baseUrl}/api/profile`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profile)
    });
    if (!res.ok) {
      throw new Error(`Update user profile failed with status ${res.status}`);
    }
    return res.json();
  }

  async triggerPlan(req: { user_id: string; message: string; session_id?: string }): Promise<Response> {
    const res = await this.tracedFetch('POST /api/plan', `${this.baseUrl}/api/plan`, {
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
    const res = await this.tracedFetch('POST /api/plan/resume', `${this.baseUrl}/api/plan/resume`, {
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

  /**
   * Submit a completed onboarding wizard directly to the orchestrator's
   * /v1/onboarding/apply endpoint (via /api/onboarding proxy). Bypasses the
   * LLM interview — writes IPS + Liabilities using the same code path the
   * LLM interview would end up in, so audit entries are identical either way.
   *
   * Resolves with { ips_id, version } on real persistence, rejects on any
   * upstream error so the UI can show a truthful failure state.
   */
  async applyOnboarding(req: {
    user_id: string;
    result: Record<string, unknown>;
    trigger?: string;
    approval_required_above_usd?: number;
    approval_required_above_percent?: number;
  }): Promise<{ status: string; ips_id: string; version: number; liabilities_count: number }> {
    const res = await this.tracedFetch('POST /api/onboarding', `${this.baseUrl}/api/onboarding`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req)
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Apply onboarding failed (${res.status}): ${text}`);
    }
    return res.json();
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
