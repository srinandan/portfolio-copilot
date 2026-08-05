import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/vue';
import Navbar from '../components/layout/Navbar.vue';
import { createRouter, createWebHistory } from 'vue-router';
import { gatewayService } from '../services/gateway';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: { template: '<div></div>' } },
    { path: '/portfolio', name: 'portfolio', component: { template: '<div></div>' } },
    { path: '/documents', name: 'documents', component: { template: '<div></div>' } },
    { path: '/security', name: 'security', component: { template: '<div></div>' } }
  ]
});

describe('Navbar.vue', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders brand title and navigation links', async () => {
    vi.spyOn(gatewayService, 'checkHealth').mockResolvedValue({ status: 'ok' });
    render(Navbar, {
      global: {
        plugins: [router]
      }
    });

    expect(screen.getByText('Portfolio Copilot')).toBeDefined();
    expect(screen.getByText('Dashboard')).toBeDefined();
    expect(screen.getByText('Portfolio')).toBeDefined();
    expect(screen.getByText('Documents')).toBeDefined();
    expect(screen.getByText('Security')).toBeDefined();
  });

  it('shows Gateway Online when checkHealth succeeds', async () => {
    vi.spyOn(gatewayService, 'checkHealth').mockResolvedValue({ status: 'ok' });
    render(Navbar, {
      global: {
        plugins: [router]
      }
    });

    await waitFor(() => {
      expect(screen.getByTestId('gateway-status').textContent).toContain('Online');
    });
  });

  it('shows Gateway Offline when checkHealth fails', async () => {
    vi.spyOn(gatewayService, 'checkHealth').mockRejectedValue(new Error('Network error'));
    render(Navbar, {
      global: {
        plugins: [router]
      }
    });

    await waitFor(() => {
      expect(screen.getByTestId('gateway-status').textContent).toContain('Offline');
    });
  });
});
