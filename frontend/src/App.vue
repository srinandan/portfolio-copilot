<template>
  <div class="min-h-screen bg-background text-on-background flex flex-col">
    <Navbar />
    <main class="pt-20 pb-16 px-4 md:px-8 max-w-7xl mx-auto w-full flex-1">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import Navbar from './components/layout/Navbar.vue';
</script>
