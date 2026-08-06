<template>
  <div class="flex flex-col w-full p-margin-mobile gap-lg max-w-2xl mx-auto" data-testid="welcome-step">
    <!-- Hero Graphic -->
    <div class="flex justify-center items-center py-xl">
      <div class="w-24 h-24 rounded-full bg-surface-container flex items-center justify-center shadow-sm relative">
        <div class="absolute inset-0 rounded-full bg-tertiary-fixed opacity-20 animate-pulse"></div>
        <span class="material-symbols-outlined text-display-lg text-on-tertiary-container" style="font-variation-settings: 'FILL' 1;">
          shield_lock
        </span>
      </div>
    </div>

    <!-- Welcome Typography -->
    <div class="flex flex-col gap-sm text-center">
      <h1 class="font-headline-lg-mobile text-on-surface">
        Welcome to Portfolio Copilot
      </h1>
      <p class="font-body-base text-on-surface-variant px-md">
        Institutional-grade portfolio governance, running locally. Your data never leaves your device.
      </p>
    </div>

    <!-- Value Props / Info Cards -->
    <div class="flex flex-col gap-md mt-md">
      <div class="bg-surface-container rounded-xl p-lg flex gap-md items-start shadow-sm relative overflow-hidden">
        <div class="w-10 h-10 rounded-full bg-surface-container-high flex items-center justify-center shrink-0">
          <span class="material-symbols-outlined text-title-sm text-on-surface">
            enhanced_encryption
          </span>
        </div>
        <div class="flex flex-col gap-xs">
          <h3 class="font-title-sm text-on-surface">Security through Privacy</h3>
          <p class="font-body-base text-on-surface-variant">
            We operate on a zero-knowledge architecture. Portfolio Copilot analyzes your positions without ever transmitting them to the cloud.
          </p>
        </div>
      </div>

      <div class="bg-surface-container rounded-xl p-lg flex gap-md items-start shadow-sm relative overflow-hidden">
        <div class="w-10 h-10 rounded-full bg-surface-container-high flex items-center justify-center shrink-0">
          <span class="material-symbols-outlined text-title-sm text-on-surface">
            no_accounts
          </span>
        </div>
        <div class="flex flex-col gap-xs">
          <h3 class="font-title-sm text-on-surface">No Bank Logins</h3>
          <p class="font-body-base text-on-surface-variant">
            Never share your credentials. You maintain absolute control by providing data via secure local file drops.
          </p>
        </div>
      </div>
    </div>

    <!-- CTA -->
    <div class="mt-lg">
      <button
        class="w-full bg-primary-container text-on-primary rounded-lg py-md px-lg flex items-center justify-center gap-sm shadow-md active:scale-[0.98] transition-transform hover:bg-primary-container/90"
        data-testid="start-setup-btn"
        @click="$emit('next')"
      >
        <span class="font-title-sm">Start Setup</span>
        <span class="material-symbols-outlined text-title-sm">
          arrow_forward
        </span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineEmits<{
  (e: 'next'): void;
}>();
</script>
