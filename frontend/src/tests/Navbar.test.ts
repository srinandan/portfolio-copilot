import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/vue';
import Navbar from '../components/layout/Navbar.vue';
import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: { template: '<div></div>' } },
    { path: '/onboarding', name: 'onboarding', component: { template: '<div></div>' } },
    { path: '/portfolio', name: 'portfolio', component: { template: '<div></div>' } },
    { path: '/spending', name: 'spending', component: { template: '<div></div>' } },
    { path: '/documents', name: 'documents', component: { template: '<div></div>' } }
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
    render(Navbar, {
      global: {
        plugins: [router]
      }
    });

    expect(screen.getByText('Portfolio Copilot')).toBeDefined();
    expect(screen.getByText('Dashboard')).toBeDefined();
    expect(screen.getByText('Onboarding')).toBeDefined();
    expect(screen.getByText('Portfolio')).toBeDefined();
    expect(screen.getByText('Spending')).toBeDefined();
    expect(screen.getByText('Documents')).toBeDefined();
  });

  it('does not display gateway status badge or profile photo', async () => {
    render(Navbar, {
      global: {
        plugins: [router]
      }
    });

    expect(screen.queryByTestId('gateway-status')).toBeNull();
    expect(screen.queryByAltText('Profile')).toBeNull();
  });
});
