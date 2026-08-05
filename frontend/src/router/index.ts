import { createRouter, createWebHistory } from 'vue-router';
import DashboardView from '../views/DashboardView.vue';
import PortfolioView from '../views/PortfolioView.vue';
import SpendingView from '../views/SpendingView.vue';
import DocumentsView from '../views/DocumentsView.vue';
import SecurityView from '../views/SecurityView.vue';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: DashboardView
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
      path: '/security',
      name: 'security',
      component: SecurityView
    }
  ]
});

export default router;
