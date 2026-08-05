import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/vue';
import DriftReportCard from '../components/portfolio/DriftReportCard.vue';
import type { DriftReport } from '../types';

describe('DriftReportCard.vue', () => {
  afterEach(() => {
    cleanup();
  });

  const sampleReport: DriftReport = {
    as_of: '2023-10-24',
    has_active_ips: true,
    rebalance_recommended: true,
    unclassified_value_usd: 1250.5,
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
        current_percent: 24.5,
        target_percent: 25.0,
        min_percent: 20.0,
        max_percent: 30.0,
        in_band: true,
        drift_amount_percent: 0.0
      }
    ]
  };

  it('renders PASS pill when asset class is within IPS target band and DRIFTED pill when out of band', () => {
    render(DriftReportCard, {
      props: { driftReport: sampleReport }
    });

    expect(screen.getByText('Equities (US)')).toBeDefined();
    expect(screen.getByText('Equities (Intl)')).toBeDefined();

    const pills = screen.getAllByTestId('status-pill');
    const pillTexts = pills.map((p) => p.textContent);
    expect(pillTexts.some((t) => t?.includes('DRIFTED'))).toBe(true);
    expect(pillTexts.some((t) => t?.includes('PASS'))).toBe(true);
  });

  it('renders Rebalancing Recommended banner when rebalance_recommended is true', () => {
    render(DriftReportCard, {
      props: { driftReport: sampleReport }
    });

    const banner = screen.getByTestId('rebalance-banner');
    expect(banner.textContent).toContain('Rebalancing Recommended: Drift exceeds IPS threshold');
  });

  it('displays unclassified_value_usd without omitting from totals', () => {
    render(DriftReportCard, {
      props: { driftReport: sampleReport }
    });

    const footer = screen.getByTestId('unclassified-value');
    expect(footer.textContent).toContain('Unclassified Holdings Value:');
    expect(footer.textContent).toContain('$1,250.50');
  });

  it('renders No investment policy set yet when has_active_ips is false', () => {
    const noIpsReport: DriftReport = {
      as_of: '2023-10-24',
      has_active_ips: false,
      rebalance_recommended: false,
      unclassified_value_usd: 0,
      bands: []
    };

    render(DriftReportCard, {
      props: { driftReport: noIpsReport }
    });

    expect(screen.getByTestId('no-ips-message').textContent).toContain('No investment policy set yet');
    expect(screen.queryByTestId('drift-table')).toBeNull();
  });
});
