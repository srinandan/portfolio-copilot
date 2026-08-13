import { createRouter, createWebHistory } from 'vue-router';
import DashboardView from '../views/DashboardView.vue';
import PortfolioView from '../views/PortfolioView.vue';
import SpendingView from '../views/SpendingView.vue';
import DocumentsView from '../views/DocumentsView.vue';
import OnboardingView from '../views/OnboardingView.vue';
import ProfileView from '../views/ProfileView.vue';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: DashboardView
    },
    {
      path: '/onboarding',
      name: 'onboarding',
      component: OnboardingView
    },
    {
      path: '/portfolio',
      name: 'portfolio',
      component: PortfolioView
    },
    {
      path: '/spending',
      name: 'spending',
      component: SpendingView
    },
    {
      path: '/documents',
      name: 'documents',
      component: DocumentsView
    },
    {
      path: '/profile',
      name: 'profile',
      component: ProfileView
    }
  ]
});

export default router;
