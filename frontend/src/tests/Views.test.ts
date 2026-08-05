import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/vue';
import DashboardView from '../views/DashboardView.vue';
import PortfolioView from '../views/PortfolioView.vue';
import DocumentsView from '../views/DocumentsView.vue';
import SecurityView from '../views/SecurityView.vue';
import { gatewayService } from '../services/gateway';

describe('Frontend Views', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(gatewayService, 'getDocuments').mockResolvedValue([
      {
        id: 'doc-1',
        filename: 'Fidelity_Stmt_Oct2023.pdf',
        size_bytes: 1258291,
        uploaded_at: '2023-10-24T09:41:00Z',
        status: 'SUCCESS',
        records_parsed: 42
      }
    ]);
    vi.spyOn(gatewayService, 'getHoldings').mockResolvedValue({
      total_value_usd: 1248500.0,
      cash_usd: 62400.0,
      as_of: '2023-10-24',
      positions: [
        {
          ticker: 'AAPL',
          name: 'Apple Inc.',
          asset_class: 'Equities (US)',
          quantity: 120,
          current_price_usd: 170.41,
          current_value_usd: 20449.2,
          change_percent: 1.2
        }
      ]
    });
    vi.spyOn(gatewayService, 'getDriftReport').mockResolvedValue({
      as_of: '2023-10-24',
      has_active_ips: true,
      rebalance_recommended: true,
      unclassified_value_usd: 0.0,
      bands: []
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('DashboardView renders agent activity stream and financial canvas', async () => {
    render(DashboardView);
    expect(screen.getByText('Agent Activity Stream')).toBeDefined();
    expect(screen.getByText('Total Net Worth')).toBeDefined();
    expect(screen.getByText('Asset Allocation')).toBeDefined();

    expect(screen.getByTestId('approval-card')).toBeDefined();
  });

  it('DashboardView allows approving and rejecting drafted actions in stream', async () => {
    render(DashboardView);
    const approveBtn = screen.getByTestId('btn-approve');
    await fireEvent.click(approveBtn);

    expect(screen.getByText(/APPROVED — Execution Triggered/i)).toBeDefined();
  });

  it('PortfolioView renders total value chart and top holdings list', async () => {
    render(PortfolioView);
    expect(screen.getByText('Total Value')).toBeDefined();
    expect(screen.getByText('Portfolio Drift Report')).toBeDefined();
    expect(screen.getByText('Top Holdings')).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText('$1,248,500.00')).toBeDefined();
    });
  });

  it('DocumentsView renders recognized formats and processing log, and supports clearing log', async () => {
    render(DocumentsView);
    expect(screen.getByText('Recognized Formats')).toBeDefined();
    expect(screen.getByText('Processing Log')).toBeDefined();

    await waitFor(() => {
      expect(screen.getAllByTestId('doc-item').length).toBeGreaterThan(0);
    });

    const clearBtn = screen.getByText('CLEAR ALL');
    await fireEvent.click(clearBtn);

    expect(screen.getByText('No documents uploaded yet.')).toBeDefined();
  });

  it('SecurityView renders privacy intro, 2FA toggle, and export button', async () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    render(SecurityView);

    expect(screen.getByText('Security Through Privacy')).toBeDefined();
    expect(screen.getByText('Two-Factor Authentication')).toBeDefined();

    const exportBtn = screen.getByText('Export Encrypted Backup');
    await fireEvent.click(exportBtn);
    expect(alertSpy).toHaveBeenCalledWith('Backup export initiated. Check your downloads.');
  });
});
