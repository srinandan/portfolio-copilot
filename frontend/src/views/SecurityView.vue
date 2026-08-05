<template>
  <div class="flex flex-col gap-lg w-full max-w-2xl mx-auto">
    <!-- Header / Intro Section -->
    <section class="flex flex-col items-center justify-center py-xl gap-md text-center">
      <div class="w-16 h-16 rounded-full bg-secondary-container flex items-center justify-center mb-sm">
        <img alt="Security Shield" class="w-8 h-8 object-contain" src="/images/security_icon.png" />
      </div>
      <h1 class="font-headline-lg-mobile text-headline-lg-mobile text-on-background">Security Through Privacy</h1>
      <p class="font-body-base text-body-base text-on-surface-variant max-w-md mx-auto">
        Your financial life, air-gapped. By relying on manual entry rather than bank connections, your core accounts remain completely offline, immune to digital breaches.
      </p>
    </section>

    <!-- Security Settings Cards -->
    <section class="flex flex-col gap-md">
      <!-- 2FA Setting -->
      <div class="bg-surface-container rounded-xl p-md flex flex-col gap-sm shadow-sm">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-sm">
            <span class="material-symbols-outlined text-secondary">phonelink_lock</span>
            <h3 class="font-title-sm text-title-sm text-on-surface">Two-Factor Authentication</h3>
          </div>
          <button
            type="button"
            :class="[
              'w-12 h-6 rounded-full relative transition-colors duration-200 cursor-pointer',
              tfaEnabled ? 'bg-primary' : 'bg-surface-variant'
            ]"
            data-testid="toggle-2fa"
            @click="tfaEnabled = !tfaEnabled"
          >
            <div
              :class="[
                'w-4 h-4 rounded-full absolute top-1 left-1 transition-transform',
                tfaEnabled ? 'bg-on-primary translate-x-6' : 'bg-outline translate-x-0'
              ]"
            ></div>
          </button>
        </div>
        <p class="font-body-base text-body-base text-on-surface-variant">
          Require a one-time code from your authenticator app when logging in from new devices.
        </p>
      </div>

      <!-- Encryption Setting -->
      <div class="bg-surface-container rounded-xl p-md flex flex-col gap-sm shadow-sm">
        <div class="flex items-center gap-sm mb-xs">
          <span class="material-symbols-outlined text-secondary">enhanced_encryption</span>
          <h3 class="font-title-sm text-title-sm text-on-surface">Data Encryption Level</h3>
        </div>
        <p class="font-body-base text-body-base text-on-surface-variant mb-sm">Choose how your local portfolio data is secured.</p>
        <div class="flex flex-col gap-xs">
          <label class="flex items-center justify-between p-sm rounded-lg bg-surface hover:bg-surface-bright cursor-pointer">
            <span class="font-body-mono text-body-mono text-on-surface">Standard (AES-256)</span>
            <input v-model="encryptionLevel" class="accent-primary w-4 h-4" name="encryption" type="radio" value="standard" />
          </label>
          <label class="flex items-center justify-between p-sm rounded-lg bg-surface hover:bg-surface-bright cursor-pointer">
            <div class="flex flex-col">
              <span class="font-body-mono text-body-mono text-on-surface">Maximum (Hardware Backed)</span>
              <span class="font-label-caps text-label-caps text-tertiary-container mt-1">Requires Biometrics</span>
            </div>
            <input v-model="encryptionLevel" class="accent-primary w-4 h-4" name="encryption" type="radio" value="maximum" />
          </label>
        </div>
      </div>

      <!-- Data Export -->
      <button
        class="bg-secondary-container text-on-secondary-container rounded-xl p-md flex items-center justify-between shadow-sm active:scale-[0.98] transition-transform w-full"
        @click="exportBackup"
      >
        <div class="flex items-center gap-sm">
          <span class="material-symbols-outlined">download</span>
          <span class="font-title-sm text-title-sm">Export Encrypted Backup</span>
        </div>
        <span class="material-symbols-outlined">chevron_right</span>
      </button>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const tfaEnabled = ref(true);
const encryptionLevel = ref('standard');

function exportBackup() {
  alert('Backup export initiated. Check your downloads.');
}
</script>
