<template>
  <header
    :class="[
      'fixed top-0 inset-x-0 z-50 bg-surface-container-lowest/95 backdrop-blur-md border-b transition-shadow duration-200 ease-desk',
      isScrolled ? 'border-outline-variant shadow-nav-scrolled' : 'border-outline-variant/80'
    ]"
  >
    <div class="max-w-7xl mx-auto h-16 px-4 md:px-8 flex items-center justify-between gap-md">
      <!-- Brand Masthead: bespoke geometric SVG mark + Newsreader wordmark -->
      <router-link
        to="/"
        class="flex items-center gap-2.5 shrink-0 group focus-visible:rounded-md"
        @click="mobileMenuOpen = false"
      >
        <svg
          class="w-7 h-7 shrink-0"
          viewBox="0 0 28 28"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <path
            d="M14 2.5L24 6.5V13.8C24 19.6 19.8 24.4 14 26C8.2 24.4 4 19.6 4 13.8V6.5L14 2.5Z"
            fill="#0F2342"
          />
          <path
            d="M8.75 16.75L12.25 13.25L15 15.75L19.5 10.75"
            stroke="#D1FAE5"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <path
            d="M16.5 10.75H19.5V13.75"
            stroke="#D1FAE5"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
        <span class="font-display text-brand font-semibold text-primary tracking-tight">
          Portfolio Copilot
        </span>
      </router-link>

      <!-- Single-line Desktop Navigation -->
      <nav aria-label="Primary navigation" class="hidden md:flex items-center gap-1 h-full">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="relative h-full inline-flex items-center px-3.5 font-sans text-body transition-colors duration-200 ease-desk"
          :class="[
            isActive(item.path)
              ? 'text-primary font-semibold'
              : 'text-on-surface-variant hover:text-on-surface font-medium'
          ]"
        >
          {{ item.name }}
          <span
            v-if="isActive(item.path)"
            class="absolute bottom-0 inset-x-3 h-[2px] bg-primary rounded-t-full"
            aria-hidden="true"
          ></span>
        </router-link>
      </nav>

      <!-- Mobile Menu Toggle -->
      <button
        type="button"
        class="md:hidden inline-flex items-center justify-center w-10 h-10 rounded-md text-on-surface hover:bg-surface-container-low transition-colors duration-200 ease-desk"
        :aria-expanded="mobileMenuOpen"
        aria-label="Toggle navigation menu"
        data-testid="mobile-nav-toggle"
        @click="mobileMenuOpen = !mobileMenuOpen"
      >
        <span class="material-symbols-outlined text-[22px]" aria-hidden="true">
          {{ mobileMenuOpen ? 'close' : 'menu' }}
        </span>
      </button>
    </div>

    <!-- Mobile Navigation Drawer -->
    <nav
      v-if="mobileMenuOpen"
      aria-label="Mobile navigation"
      class="md:hidden bg-surface-container-lowest border-t border-outline-variant px-4 py-2 flex flex-col divide-y divide-outline-variant/60"
      data-testid="mobile-nav-drawer"
    >
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="py-3 px-2 font-sans text-body flex items-center justify-between transition-colors duration-200 ease-desk"
        :class="[
          isActive(item.path)
            ? 'text-primary font-semibold'
            : 'text-on-surface-variant hover:text-on-surface'
        ]"
        @click="mobileMenuOpen = false"
      >
        <span>{{ item.name }}</span>
        <span
          v-if="isActive(item.path)"
          class="w-1.5 h-1.5 rounded-full bg-primary"
          aria-hidden="true"
        ></span>
      </router-link>
    </nav>
  </header>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const mobileMenuOpen = ref(false);
const isScrolled = ref(false);

const navItems = [
  { name: 'Dashboard', path: '/' },
  { name: 'Portfolio', path: '/portfolio' },
  { name: 'Spending', path: '/spending' },
  { name: 'Documents', path: '/documents' },
  { name: 'Profile', path: '/profile' }
];

function isActive(path: string): boolean {
  return route.path === path;
}

function onScroll() {
  isScrolled.value = window.scrollY > 8;
}

onMounted(() => {
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });
});

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll);
});
</script>
