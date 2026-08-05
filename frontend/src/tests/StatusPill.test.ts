import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/vue';
import StatusPill from '../components/common/StatusPill.vue';

describe('StatusPill.vue', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders emerald styling for APPROVED status', () => {
    render(StatusPill, {
      props: { status: 'APPROVED' }
    });
    const pill = screen.getByTestId('status-pill');
    expect(pill.textContent).toContain('APPROVED');
    expect(pill.className).toContain('bg-tertiary-fixed');
  });

  it('renders amber styling for PENDING status', () => {
    render(StatusPill, {
      props: { status: 'PENDING' }
    });
    const pill = screen.getByTestId('status-pill');
    expect(pill.textContent).toContain('PENDING');
    expect(pill.className).toContain('bg-secondary-fixed');
  });

  it('renders crimson styling for VIOLATION status', () => {
    render(StatusPill, {
      props: { status: 'VIOLATION' }
    });
    const pill = screen.getByTestId('status-pill');
    expect(pill.textContent).toContain('VIOLATION');
    expect(pill.className).toContain('bg-error-container');
  });

  it('renders custom label when provided', () => {
    render(StatusPill, {
      props: { status: 'APPROVED', label: 'VERIFIED OK' }
    });
    expect(screen.getByTestId('status-pill').textContent).toContain('VERIFIED OK');
  });
});
