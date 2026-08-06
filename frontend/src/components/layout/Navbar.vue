<template>
  <header class="fixed top-0 w-full z-50 bg-surface/80 backdrop-blur-xl pt-safe shadow-[0_1px_8px_rgba(0,0,0,0.04)] border-b border-outline/10">
    <div class="h-16 px-md md:px-xl flex items-center justify-between">
      <div class="flex items-center gap-lg">
        <router-link to="/" class="flex items-center gap-sm">
          <img alt="Portfolio Copilot Logo" class="h-8 w-auto object-contain" src="/images/logo.png" />
          <span class="font-title-sm text-title-sm text-primary">Portfolio Copilot</span>
        </router-link>
        <nav class="hidden md:flex items-center gap-md">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="font-body-base text-sm px-3 py-1.5 rounded-lg transition-colors"
            :class="[
              $route.path === item.path
                ? 'bg-primary-container text-on-primary font-medium'
                : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
            ]"
          >
            {{ item.name }}
          </router-link>
        </nav>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
const navItems = [
  { name: 'Dashboard', path: '/' },
  { name: 'Onboarding', path: '/onboarding' },
  { name: 'Portfolio', path: '/portfolio' },
  { name: 'Spending', path: '/spending' },
  { name: 'Documents', path: '/documents' },
  { name: 'Security', path: '/security' }
];
</script>
