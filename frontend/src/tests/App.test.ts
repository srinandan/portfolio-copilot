import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/vue';
import App from '../App.vue';
import router from '../router';

describe('App.vue', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders navbar and root application layout', async () => {
    router.push('/');
    await router.isReady();

    render(App, {
      global: {
        plugins: [router]
      }
    });

    expect(screen.getByText('Portfolio Copilot')).toBeDefined();
    expect(screen.getByText('Dashboard')).toBeDefined();
  });
});
