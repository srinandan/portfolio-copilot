<template>
  <section class="bg-surface-container-lowest rounded-xl shadow-sm border border-surface-variant flex flex-col" data-testid="upload-dropzone">
    <div class="p-md border-b border-surface-variant flex items-center justify-between">
      <h2 class="font-headline-md text-headline-md text-on-surface">Secure Document Ingestion</h2>
      <span class="material-symbols-outlined text-outline">verified_user</span>
    </div>
    <div class="p-lg">
      <div class="mb-md grid grid-cols-1 md:grid-cols-2 gap-md">
        <div class="flex flex-col gap-xs">
          <label for="document-type-select" class="font-body-base text-xs font-label-caps uppercase text-on-surface-variant">Document Type</label>
          <select
            id="document-type-select"
            v-model="documentType"
            class="bg-surface-container-low text-on-surface border border-outline-variant rounded-md px-sm py-xs text-sm font-body-base focus:outline-none focus:border-primary"
            data-testid="account-type-select"
            @change="selectedFile = null"
          >
            <option value="transactions">Checking / Card Transactions (CSV → BigQuery)</option>
            <option value="holdings">Brokerage Holdings Snapshot (JSON → Firestore)</option>
            <option value="liabilities">Debts &amp; Liabilities (JSON → Firestore)</option>
            <option value="ips">Investment Policy Statement (JSON → Firestore)</option>
          </select>
        </div>

        <div v-if="documentType === 'transactions'" class="flex flex-col gap-xs">
          <label for="target-table-select" class="font-body-base text-xs font-label-caps uppercase text-on-surface-variant">Target BigQuery Table</label>
          <select
            id="target-table-select"
            v-model="targetTable"
            class="bg-surface-container-low text-on-surface border border-outline-variant rounded-md px-sm py-xs text-sm font-body-base focus:outline-none focus:border-primary"
            data-testid="target-table-select"
          >
            <option value="checking_transactions">checking_transactions</option>
          </select>
        </div>
      </div>

      <div
        :class="[
          'border-2 border-dashed rounded-lg p-xl flex flex-col items-center justify-center text-center transition-colors duration-200 cursor-pointer',
          isDragging
            ? 'border-tertiary-fixed-dim bg-tertiary-fixed/10'
            : 'border-outline-variant hover:border-primary-fixed-dim hover:bg-surface-container-low'
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
        <img alt="Upload Statement Icon" class="w-16 h-16 object-contain mb-md opacity-80" src="/images/upload_icon.png" />
        <h3 class="font-title-sm text-title-sm text-on-surface mb-xs">
          {{ selectedFile ? selectedFile.name : 'Drop File Here' }}
        </h3>
        <p class="font-body-base text-body-base text-on-surface-variant mb-md max-w-sm">
          {{
            selectedFile
              ? `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB • ${documentType.toUpperCase()} (${destinationLabel})`
              : `Accepted: ${acceptedExtensions} format for ${documentTypeLabel}.`
          }}
        </p>
        <button
          type="button"
          class="bg-primary-container text-on-primary-container px-lg py-sm rounded-full font-label-caps text-label-caps shadow-sm active:opacity-80 transition-opacity uppercase"
        >
          {{ selectedFile ? 'CHANGE FILE' : 'BROWSE FILES' }}
        </button>
      </div>

      <div class="mt-md flex items-start gap-sm bg-surface-container-low p-sm rounded-md">
        <span class="material-symbols-outlined text-outline text-[18px]">privacy_tip</span>
        <p class="font-body-base text-body-base text-on-surface-variant text-sm">
          <span class="font-semibold text-on-surface">Validation &amp; Privacy:</span> Files are strictly validated against authoritative JSON and schema contracts before updating long-term stores.
        </p>
      </div>
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
