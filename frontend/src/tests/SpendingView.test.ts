import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/vue';
import SpendingView from '../views/SpendingView.vue';
import { apiService } from '../services/api';
import type { SpendingReport } from '../types';

describe('SpendingView.vue', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  const mockReport: SpendingReport = {
    user_id: 'usr_test',
    total_income_usd: 20000,
    total_outflow_usd: 14000,
    savings_rate: 0.30,
    reserve_months: 9.5,
    category_breakdown: [
      { category: 'groceries', amount_usd: 1500, percent_of_total: 15 },
      { category: 'housing', amount_usd: 4000, percent_of_total: 40 },
      { category: 'utilities', amount_usd: 500, percent_of_total: 5 }
    ],
    anomalies: [
      {
        category: 'groceries',
        amount_usd: 1500,
        trailing_average_usd: 1000,
        description: 'Groceries spend 50% above average',
        date: '2023-10-15'
      }
    ],
    narrative_summary: 'Overall healthy savings rate.'
  };

  it('renders spending summary metrics (savings rate and reserve months)', async () => {
    vi.spyOn(apiService, 'getSpendingReport').mockResolvedValue(mockReport);
    render(SpendingView);

    await waitFor(() => {
      expect(screen.getByText('30.0%')).toBeDefined();
      expect(screen.getByText('9.5 mo')).toBeDefined();
    });
  });

  it('renders category breakdown items sorted descending by amount', async () => {
    vi.spyOn(apiService, 'getSpendingReport').mockResolvedValue(mockReport);
    render(SpendingView);

    await waitFor(() => {
      const rows = screen.getAllByTestId('category-row');
      expect(rows).toHaveLength(3);
      expect(rows[0].textContent).toContain('housing');
      expect(rows[1].textContent).toContain('groceries');
      expect(rows[2].textContent).toContain('utilities');
    });
  });

  it('conditionally renders anomaly alert card when anomalies are present', async () => {
    vi.spyOn(apiService, 'getSpendingReport').mockResolvedValue(mockReport);
    render(SpendingView);

    await waitFor(() => {
      expect(screen.getByTestId('anomaly-alert-card')).toBeDefined();
      expect(screen.getByText('Spending Anomalies Detected')).toBeDefined();
    });
  });
});
