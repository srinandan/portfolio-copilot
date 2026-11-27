import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/vue';
import Navbar from '../components/layout/Navbar.vue';
import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: { template: '<div></div>' } },
    { path: '/onboarding', name: 'onboarding', component: { template: '<div></div>' } },
    { path: '/portfolio', name: 'portfolio', component: { template: '<div></div>' } },
    { path: '/spending', name: 'spending', component: { template: '<div></div>' } },
    { path: '/documents', name: 'documents', component: { template: '<div></div>' } },
    { path: '/profile', name: 'profile', component: { template: '<div></div>' } }
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
    expect(screen.getByText('Portfolio')).toBeDefined();
    expect(screen.getByText('Spending')).toBeDefined();
    expect(screen.getByText('Documents')).toBeDefined();
    expect(screen.getByText('Profile')).toBeDefined();
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

  it('toggles the mobile navigation drawer when the mobile menu button is clicked', async () => {
    render(Navbar, {
      global: {
        plugins: [router]
      }
    });

    expect(screen.queryByTestId('mobile-nav-drawer')).toBeNull();
    const toggle = screen.getByTestId('mobile-nav-toggle');
    await fireEvent.click(toggle);

    const drawer = screen.getByTestId('mobile-nav-drawer');
    expect(drawer.textContent).toContain('Dashboard');
    expect(drawer.textContent).toContain('Portfolio');
    expect(drawer.textContent).toContain('Profile');

    await fireEvent.click(toggle);
    expect(screen.queryByTestId('mobile-nav-drawer')).toBeNull();
  });
});
