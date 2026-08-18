import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/vue';
import AnalysisProgress from '../components/dashboard/AnalysisProgress.vue';
import type { ProgressStage } from '../types';

describe('AnalysisProgress.vue', () => {
  afterEach(() => {
    cleanup();
  });

  const stages: ProgressStage[] = [
    { stage: 'discovery', label: 'Discovering authorized skills', status: 'done', detail: '5 authorized skill(s)' },
    { stage: 'spending-analysis', label: 'Analyzing spending', status: 'done' },
    { stage: 'research', label: 'Researching market context', status: 'skipped' },
    { stage: 'portfolio-analysis', label: 'Analyzing portfolio drift', status: 'running' }
  ];

  it('renders one row per stage with its label', () => {
    render(AnalysisProgress, { props: { stages } });
    const rows = screen.getAllByTestId('progress-stage');
    expect(rows).toHaveLength(4);
    expect(screen.getByText('Discovering authorized skills')).toBeDefined();
    expect(screen.getByText('Analyzing portfolio drift')).toBeDefined();
  });

  it('marks each row with its status for styling/behavior', () => {
    render(AnalysisProgress, { props: { stages } });
    const byStage = (s: string) =>
      screen.getAllByTestId('progress-stage').find((r) => r.getAttribute('data-stage') === s)!;

    expect(byStage('portfolio-analysis').getAttribute('data-status')).toBe('running');
    expect(byStage('discovery').getAttribute('data-status')).toBe('done');
    expect(byStage('research').getAttribute('data-status')).toBe('skipped');
  });

  it('shows the running stage with a spinning icon', () => {
    render(AnalysisProgress, { props: { stages } });
    const running = screen
      .getAllByTestId('progress-stage')
      .find((r) => r.getAttribute('data-stage') === 'portfolio-analysis')!;
    const icon = running.querySelector('.material-symbols-outlined');
    expect(icon?.classList.contains('animate-spin')).toBe(true);
    expect(icon?.textContent).toContain('progress_activity');
  });

  it('renders a pending (not-yet-started) stage with a static hollow marker', () => {
    const withPending: ProgressStage[] = [
      { stage: 'action-drafting', label: 'Drafting proposed action', status: 'pending' }
    ];
    render(AnalysisProgress, { props: { stages: withPending } });
    const row = screen
      .getAllByTestId('progress-stage')
      .find((r) => r.getAttribute('data-stage') === 'action-drafting')!;
    expect(row.getAttribute('data-status')).toBe('pending');
    const icon = row.querySelector('.material-symbols-outlined');
    expect(icon?.textContent).toContain('radio_button_unchecked');
    expect(icon?.classList.contains('animate-spin')).toBe(false);
    expect(screen.getByText('Drafting proposed action')).toBeDefined();
  });

  it('renders optional per-stage detail text', () => {
    render(AnalysisProgress, { props: { stages } });
    expect(screen.getByText('5 authorized skill(s)')).toBeDefined();
  });

  it('renders an elapsed timer derived from startedAt', () => {
    const startedAt = Date.now() - 42_000; // 42s ago
    render(AnalysisProgress, { props: { stages, startedAt } });
    const elapsed = screen.getByTestId('analysis-elapsed');
    expect(elapsed.textContent).toMatch(/^0:4\d$/);
  });
});
