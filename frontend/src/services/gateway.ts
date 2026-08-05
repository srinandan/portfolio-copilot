import type {
  HealthStatus,
  AuthCheckResult,
  HoldingsSnapshot,
  DocumentItem,
  ProposedAction
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
    // Scaffold fallback until backend holdings endpoint is connected
    return {
      total_value_usd: 1248500.0,
      cash_usd: 62400.0,
      as_of: new Date().toISOString().split('T')[0],
      positions: [
        {
          ticker: 'AAPL',
          name: 'Apple Inc.',
          asset_class: 'Equities (US)',
          quantity: 120,
          current_price_usd: 170.41,
          current_value_usd: 20449.2,
          change_percent: 1.2
        },
        {
          ticker: 'VOO',
          name: 'Vanguard S&P 500 ETF',
          asset_class: 'Equities (US)',
          quantity: 45,
          current_price_usd: 404.45,
          current_value_usd: 18200.25,
          change_percent: 0.8
        },
        {
          ticker: 'MSFT',
          name: 'Microsoft Corp.',
          asset_class: 'Equities (US)',
          quantity: 50,
          current_price_usd: 410.0,
          current_value_usd: 20500.0,
          change_percent: -0.4
        }
      ]
    };
  }

  async getDocuments(): Promise<DocumentItem[]> {
    return [
      {
        id: 'doc-1',
        filename: 'Fidelity_Stmt_Oct2023.pdf',
        size_bytes: 1258291,
        uploaded_at: '2023-10-24T09:41:00Z',
        status: 'SUCCESS',
        records_parsed: 42
      }
    ];
  }

  async approveAction(actionId: string): Promise<ProposedAction> {
    return {
      action_id: actionId,
      session_id: 'sess-default',
      type: 'TRADE',
      status: 'APPROVED',
      rationale: 'Approved by human in UI.'
    };
  }

  async rejectAction(actionId: string): Promise<ProposedAction> {
    return {
      action_id: actionId,
      session_id: 'sess-default',
      type: 'TRADE',
      status: 'REJECTED',
      rationale: 'Rejected by human in UI.'
    };
  }
}

export const gatewayService = new GatewayService();
