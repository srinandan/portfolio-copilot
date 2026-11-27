<template>
  <div class="min-h-screen bg-background text-on-background flex flex-col">
    <Navbar v-if="showNavbar" />
    <main
      :class="showNavbar ? 'pt-20 pb-16 px-4 md:px-8 max-w-7xl mx-auto w-full flex-1' : 'w-full flex-1'"
    >
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import Navbar from './components/layout/Navbar.vue';

const route = useRoute();
// Onboarding renders its own dedicated fixed progress header.
const showNavbar = computed(() => route.path !== '/onboarding');
</script>
