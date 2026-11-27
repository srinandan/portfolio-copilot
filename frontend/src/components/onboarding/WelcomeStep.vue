<template>
  <div class="flex flex-col w-full gap-lg max-w-2xl mx-auto" data-testid="welcome-step">
    <!-- Brand Mark & Editorial Intro -->
    <div class="flex flex-col items-center text-center gap-3 pt-4">
      <svg
        class="w-14 h-14 mb-1"
        viewBox="0 0 56 56"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <path
          d="M28 5L48 13V27.6C48 39.2 39.6 48.8 28 52C16.4 48.8 8 39.2 8 27.6V13L28 5Z"
          fill="#0F2342"
        />
        <path
          d="M17.5 33.5L24.5 26.5L30 31.5L39 21.5"
          stroke="#D1FAE5"
          stroke-width="3.2"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <path
          d="M33 21.5H39V27.5"
          stroke="#D1FAE5"
          stroke-width="3.2"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>

      <h1 class="font-display text-page-title font-medium text-on-surface">
        Welcome to Portfolio Copilot
      </h1>
      <p class="font-sans text-body text-on-surface-variant max-w-[52ch]">
        Establish your Investment Policy Statement so every portfolio review, drift alert, and trade proposal adheres to your explicit guardrails.
      </p>
    </div>

    <!-- Principles Sheet (single hairline-divided container) -->
    <section class="bg-surface-container-lowest rounded-xl border border-outline-variant shadow-sheet divide-y divide-outline-variant overflow-hidden">
      <div class="p-lg flex gap-md items-start">
        <span class="material-symbols-outlined text-[22px] text-primary mt-0.5 shrink-0" aria-hidden="true">
          enhanced_encryption
        </span>
        <div class="flex flex-col gap-1">
          <h2 class="font-sans text-heading font-semibold text-on-surface">Security through Privacy</h2>
          <p class="font-sans text-body text-on-surface-variant max-w-[65ch]">
            Every proposed action is evaluated against your Investment Policy Statement before reaching your approval gate.
          </p>
        </div>
      </div>

      <div class="p-lg flex gap-md items-start">
        <span class="material-symbols-outlined text-[22px] text-primary mt-0.5 shrink-0" aria-hidden="true">
          no_accounts
        </span>
        <div class="flex flex-col gap-1">
          <h2 class="font-sans text-heading font-semibold text-on-surface">No Bank Logins</h2>
          <p class="font-sans text-body text-on-surface-variant max-w-[65ch]">
            Never share brokerage or bank credentials. Provide holdings and statements directly via schema-validated file uploads.
          </p>
        </div>
      </div>
    </section>

    <!-- Active IPS Notice -->
    <div
      v-if="hasActiveProfile"
      class="bg-tertiary-fixed/50 border border-tertiary-fixed-dim rounded-xl px-lg py-4 flex gap-3 items-start text-on-tertiary-fixed"
      data-testid="active-ips-banner"
    >
      <span class="material-symbols-outlined text-[20px] text-on-tertiary-container mt-0.5 shrink-0" aria-hidden="true">
        verified_user
      </span>
      <p class="font-sans text-body">
        <span class="font-semibold">Active IPS (v{{ activeVersion || 1 }}) Found:</span>
        Your current goals, target bands, and guardrails have been pre-filled. Proceed to review or update.
      </p>
    </div>

    <!-- Primary CTA -->
    <div>
      <button
        type="button"
        class="w-full bg-primary text-on-primary rounded-md py-3.5 px-lg font-sans text-body font-medium inline-flex items-center justify-center gap-2 transition-[background-color,transform] duration-200 ease-desk hover:bg-primary-container active:scale-[0.99]"
        data-testid="start-setup-btn"
        @click="$emit('next')"
      >
        <span>{{ hasActiveProfile ? 'Review & Edit Policy' : 'Start Setup' }}</span>
        <span class="material-symbols-outlined text-[18px]" aria-hidden="true">arrow_forward</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    hasActiveProfile?: boolean;
    activeVersion?: number;
  }>(),
  {
    hasActiveProfile: false,
    activeVersion: 1
  }
);

defineEmits<{
  (e: 'next'): void;
}>();
</script>
