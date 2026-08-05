import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/vue';
import DashboardView from '../views/DashboardView.vue';
import PortfolioView from '../views/PortfolioView.vue';
import DocumentsView from '../views/DocumentsView.vue';
import SecurityView from '../views/SecurityView.vue';

describe('Frontend Views', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
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
