import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/vue';
import Button from '../components/common/Button.vue';

describe('Button.vue', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders slot text and primary styling by default', () => {
    render(Button, {
      slots: { default: 'Click Me' }
    });
    const btn = screen.getByTestId('ui-button');
    expect(btn.textContent).toContain('Click Me');
    expect(btn.className).toContain('bg-primary');
  });

  it('renders approval variant styling', () => {
    render(Button, {
      props: { variant: 'approval' },
      slots: { default: 'Approve' }
    });
    const btn = screen.getByTestId('ui-button');
    expect(btn.className).toContain('bg-tertiary-fixed');
  });

  it('renders danger variant styling', () => {
    render(Button, {
      props: { variant: 'danger' },
      slots: { default: 'Reject' }
    });
    const btn = screen.getByTestId('ui-button');
    expect(btn.className).toContain('border-error');
  });

  it('emits click event when clicked', async () => {
    const { emitted } = render(Button, {
      slots: { default: 'Click' }
    });
    await fireEvent.click(screen.getByTestId('ui-button'));
    expect(emitted().click).toHaveLength(1);
  });

  it('does not emit click when disabled', async () => {
    const { emitted } = render(Button, {
      props: { disabled: true },
      slots: { default: 'Disabled' }
    });
    const btn = screen.getByTestId('ui-button');
    expect(btn.className).toContain('opacity-50');
    expect((btn as HTMLButtonElement).disabled).toBe(true);
    await fireEvent.click(btn);
    expect(emitted().click).toBeUndefined();
  });
});
