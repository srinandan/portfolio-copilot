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

  async getSpendingReport(): Promise<SpendingReport> {
    return {
      user_id: 'usr_default',
      total_income_usd: 18500.0,
      total_outflow_usd: 13227.5,
      savings_rate: 0.285,
      reserve_months: 8.2,
      category_breakdown: [
        { category: 'housing', amount_usd: 4200.0, percent_of_total: 31.8, monthly_average_usd: 4200.0 },
        { category: 'dining', amount_usd: 2150.0, percent_of_total: 16.3, monthly_average_usd: 1350.0 },
        { category: 'groceries', amount_usd: 1680.0, percent_of_total: 12.7, monthly_average_usd: 1650.0 },
        { category: 'transportation', amount_usd: 1240.0, percent_of_total: 9.4, monthly_average_usd: 1200.0 },
        { category: 'utilities', amount_usd: 620.0, percent_of_total: 4.7, monthly_average_usd: 600.0 },
        { category: 'other', amount_usd: 3337.5, percent_of_total: 25.1, monthly_average_usd: 3100.0 }
      ],
      anomalies: [
        {
          category: 'dining',
          amount_usd: 2150.0,
          trailing_average_usd: 1350.0,
          description: 'Dining spend jumped 59% above trailing 3-month average ($1,350/mo)',
          date: '2023-10-15'
        }
      ],
      narrative_summary:
        'Spending is well-controlled with a healthy 28.5% savings rate and 8.2 months of cash liquidity. However, dining expenditures exceeded trailing averages by $800 this month.'
    };
  }

  async getDriftReport(): Promise<DriftReport> {
    return {
      as_of: '2023-10-24',
      has_active_ips: true,
      rebalance_recommended: true,
      unclassified_value_usd: 0.0,
      bands: [
        {
          asset_class: 'Equities (US)',
          current_percent: 58.4,
          target_percent: 55.0,
          min_percent: 50.0,
          max_percent: 58.0,
          in_band: false,
          drift_amount_percent: 3.4
        },
        {
          asset_class: 'Equities (Intl)',
          current_percent: 23.6,
          target_percent: 25.0,
          min_percent: 20.0,
          max_percent: 30.0,
          in_band: true,
          drift_amount_percent: 0.0
        },
        {
          asset_class: 'Fixed Income',
          current_percent: 13.0,
          target_percent: 15.0,
          min_percent: 10.0,
          max_percent: 20.0,
          in_band: true,
          drift_amount_percent: 0.0
        },
        {
          asset_class: 'Cash/Equiv',
          current_percent: 5.0,
          target_percent: 5.0,
          min_percent: 2.0,
          max_percent: 10.0,
          in_band: true,
          drift_amount_percent: 0.0
        }
      ]
    };
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
