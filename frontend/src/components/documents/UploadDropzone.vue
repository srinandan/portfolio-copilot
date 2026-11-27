<template>
  <section
    class="bg-surface-container-lowest rounded-xl shadow-sheet border border-outline-variant flex flex-col overflow-hidden"
    data-testid="upload-dropzone"
  >
    <div class="px-lg py-4 border-b border-outline-variant flex items-center justify-between gap-md">
      <h2 class="font-sans text-heading font-semibold text-on-surface">Secure Document Ingestion</h2>
      <span class="material-symbols-outlined text-[20px] text-primary" aria-hidden="true">verified_user</span>
    </div>

    <div class="p-lg flex flex-col gap-md">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
        <div class="flex flex-col gap-1.5">
          <label for="document-type-select" class="font-sans text-meta font-medium text-on-surface-variant">
            Document type
          </label>
          <select
            id="document-type-select"
            v-model="documentType"
            class="bg-surface text-on-surface border border-outline-variant rounded-md px-3 py-2 text-body font-sans transition-colors duration-200 ease-desk focus:bg-surface-container-lowest"
            data-testid="account-type-select"
            @change="selectedFile = null"
          >
            <option value="transactions">Checking / Card Transactions (CSV to BigQuery)</option>
            <option value="holdings">Brokerage Holdings Snapshot (JSON to Firestore)</option>
            <option value="liabilities">Debts &amp; Liabilities (JSON to Firestore)</option>
            <option value="ips">Investment Policy Statement (JSON to Firestore)</option>
          </select>
        </div>

        <div v-if="documentType === 'transactions'" class="flex flex-col gap-1.5">
          <label for="target-table-select" class="font-sans text-meta font-medium text-on-surface-variant">
            Target BigQuery table
          </label>
          <select
            id="target-table-select"
            v-model="targetTable"
            class="bg-surface text-on-surface border border-outline-variant rounded-md px-3 py-2 text-body font-sans transition-colors duration-200 ease-desk focus:bg-surface-container-lowest"
            data-testid="target-table-select"
          >
            <option value="checking_transactions">checking_transactions</option>
          </select>
        </div>
      </div>

      <div
        :class="[
          'border-2 border-dashed rounded-lg p-xl flex flex-col items-center justify-center text-center transition-[border-color,background-color] duration-200 ease-desk cursor-pointer',
          isDragging
            ? 'border-on-tertiary-container bg-tertiary-fixed/30'
            : 'border-outline-variant bg-surface/60 hover:border-primary/60 hover:bg-surface-container-low/60'
        ]"
        data-testid="dropzone"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="onDrop"
        @click="triggerFileInput"
      >
        <input
          ref="fileInputRef"
          type="file"
          class="hidden"
          :accept="acceptedExtensions"
          data-testid="file-input"
          @change="onFileSelect"
        />

        <!-- Bespoke geometric SVG upload mark -->
        <svg
          class="w-12 h-12 mb-3 text-primary"
          viewBox="0 0 48 48"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <rect x="8" y="6" width="32" height="36" rx="4" stroke="currentColor" stroke-width="2" fill="#FFFFFF" />
          <path d="M24 31V18" stroke="#1E40AF" stroke-width="2.2" stroke-linecap="round" />
          <path d="M18.5 23L24 17.5L29.5 23" stroke="#1E40AF" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M16 35H32" stroke="#D5DDE6" stroke-width="2" stroke-linecap="round" />
        </svg>

        <h3 class="font-sans text-heading font-semibold text-on-surface mb-1">
          {{ selectedFile ? selectedFile.name : 'Drop File Here' }}
        </h3>
        <p class="font-sans text-body text-on-surface-variant mb-4 max-w-[46ch] tabular-nums">
          {{
            selectedFile
              ? `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB · ${documentType} (${destinationLabel})`
              : `Accepted format: ${acceptedExtensions} for ${documentTypeLabel}.`
          }}
        </p>
        <button
          type="button"
          class="bg-primary text-on-primary px-5 py-2 rounded-md font-sans text-body font-medium hover:bg-primary-container transition-colors duration-200 ease-desk"
        >
          {{ selectedFile ? 'Change file' : 'Browse files' }}
        </button>
      </div>
    </div>

    <div class="px-lg py-3.5 border-t border-outline-variant bg-surface-container-low/40 flex items-start gap-2.5">
      <span class="material-symbols-outlined text-outline text-[18px] mt-0.5 shrink-0" aria-hidden="true">
        privacy_tip
      </span>
      <p class="font-sans text-meta text-on-surface-variant max-w-[65ch]">
        <span class="font-semibold text-on-surface">Validation &amp; Privacy:</span>
        Files are strictly validated against authoritative JSON and schema contracts before updating long-term stores.
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';

const emit = defineEmits<{
  (e: 'file-selected', file: File, documentType: string, targetTable?: string): void;
}>();

const isDragging = ref(false);
const selectedFile = ref<File | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);
const documentType = ref<'transactions' | 'holdings' | 'liabilities' | 'ips'>('transactions');
const targetTable = ref<'checking_transactions'>('checking_transactions');

const acceptedExtensions = computed(() => {
  return documentType.value === 'transactions' ? '.csv' : '.json';
});

const documentTypeLabel = computed(() => {
  switch (documentType.value) {
    case 'transactions':
      return 'Account Transactions';
    case 'holdings':
      return 'Brokerage Holdings';
    case 'liabilities':
      return 'Debts & Liabilities';
    case 'ips':
      return 'Investment Policy Statement';
  }
});

const destinationLabel = computed(() => {
  switch (documentType.value) {
    case 'transactions':
      return `BigQuery: ${targetTable.value}`;
    case 'holdings':
      return 'Firestore: holdings/{user_id}';
    case 'liabilities':
      return 'Firestore: liabilities/{user_id}';
    case 'ips':
      return 'Firestore: ips/{ips_id}';
  }
});

function triggerFileInput() {
  fileInputRef.value?.click();
}

function handleFile(file: File) {
  selectedFile.value = file;
  emit(
    'file-selected',
    file,
    documentType.value,
    documentType.value === 'transactions' ? targetTable.value : undefined
  );
}

function onFileSelect(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files[0]) {
    handleFile(target.files[0]);
  }
}

function onDrop(event: DragEvent) {
  isDragging.value = false;
  if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
    handleFile(event.dataTransfer.files[0]);
  }
}
</script>
