import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/vue';
import NetWorthCard from '../components/dashboard/NetWorthCard.vue';

describe('NetWorthCard.vue', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders default zero net worth with display tabular typography', () => {
    render(NetWorthCard);
    const valueEl = screen.getByTestId('net-worth-value');
    expect(valueEl.textContent?.trim()).toBe('$0.00');
    expect(valueEl.className).toContain('font-display');
    expect(valueEl.className).toContain('tabular-nums');
  });

  it('renders optional cash balance breakdown when cashUsd is positive', () => {
    render(NetWorthCard, {
      props: { totalValue: 100000, cashUsd: 12500.5 }
    });
    expect(screen.getByText(/Includes \$12,500\.50 in cash and equivalents/)).toBeDefined();
  });

  it('renders formatted net worth with commas and 2 decimal places', () => {
    render(NetWorthCard, {
      props: { totalValue: 1248500.5 }
    });
    const valueEl = screen.getByTestId('net-worth-value');
    expect(valueEl.textContent?.trim()).toBe('$1,248,500.50');
  });

  it('renders formatted asOf timestamp when provided', () => {
    render(NetWorthCard, {
      props: {
        totalValue: 500000,
        asOf: '2026-08-15T14:30:00Z'
      }
    });
    expect(screen.getByText(/Updated Aug 15, 2026/)).toBeDefined();
  });

  it('renders fallback asOf string when unparseable date is provided', () => {
    render(NetWorthCard, {
      props: {
        totalValue: 500000,
        asOf: 'Q3 2026'
      }
    });
    expect(screen.getByText('As of Q3 2026')).toBeDefined();
  });
});
