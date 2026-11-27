<template>
  <div class="flex flex-col gap-lg w-full" data-testid="documents-view">
    <header class="flex flex-col gap-1">
      <h1 class="font-display text-page-title font-medium text-on-background">Documents &amp; File Ingestion</h1>
      <p class="font-sans text-body text-on-surface-variant max-w-[65ch]">
        Upload bank transactions (CSV) or balance and IPS snapshots (JSON). Every file is validated against schema contracts before writing to BigQuery or Firestore.
      </p>
    </header>

    <!-- Upload Status Alerts -->
    <div
      v-if="uploadSuccess"
      class="bg-tertiary-fixed/50 border border-tertiary-fixed-dim text-on-tertiary-fixed px-md py-3 rounded-lg flex items-center justify-between gap-md"
      data-testid="upload-success-alert"
    >
      <div class="flex items-center gap-2.5">
        <span class="material-symbols-outlined text-[20px] text-on-tertiary-container" aria-hidden="true">check_circle</span>
        <div class="font-sans text-body tabular-nums">
          <span class="font-semibold">Ingestion successful:</span>
          Parsed <span class="font-semibold">{{ uploadSuccess.records_parsed ?? 0 }}</span> records from
          <span class="font-medium">{{ uploadSuccess.filename }}</span> into
          {{ uploadSuccess.target_table || uploadSuccess.document_type || uploadSuccess.account_type }}.
        </div>
      </div>
      <button
        type="button"
        class="font-sans text-meta font-medium hover:underline shrink-0"
        @click="uploadSuccess = null"
      >
        Dismiss
      </button>
    </div>

    <div
      v-if="uploadError"
      class="bg-error-container border border-error/30 text-on-error-container px-md py-3 rounded-lg flex items-center justify-between gap-md"
      data-testid="upload-error-alert"
    >
      <div class="flex items-center gap-2.5">
        <span class="material-symbols-outlined text-[20px]" aria-hidden="true">error</span>
        <div class="font-sans text-body">
          <span class="font-semibold">Upload failed:</span> {{ uploadError }}
        </div>
      </div>
      <button
        type="button"
        class="font-sans text-meta font-medium hover:underline shrink-0"
        @click="uploadError = null"
      >
        Dismiss
      </button>
    </div>

    <!-- Dropzone -->
    <UploadDropzone
      :uploading="isUploading"
      @file-selected="onFileSelected"
    />

    <!-- Document History Ledger -->
    <section class="bg-surface-container-lowest rounded-xl border border-outline-variant shadow-sheet overflow-hidden flex flex-col">
      <div class="px-lg py-4 border-b border-outline-variant flex items-center justify-between gap-md">
        <h2 class="font-sans text-heading font-semibold text-on-surface">Ingested Documents History</h2>
        <button
          type="button"
          class="font-sans text-meta font-medium text-primary hover:bg-surface-container-low px-3 py-1.5 rounded-md inline-flex items-center gap-1.5 transition-colors duration-150 ease-desk"
          data-testid="refresh-documents-btn"
          @click="loadDocuments"
        >
          <span class="material-symbols-outlined text-[16px]" aria-hidden="true">refresh</span>
          Refresh
        </button>
      </div>

      <div v-if="loading" class="p-xl text-center text-on-surface-variant font-sans text-body">
        Loading documents...
      </div>

      <div v-else-if="documents.length === 0" class="p-xl text-center text-on-surface-variant font-sans text-body">
        No documents uploaded yet. Upload a statement or snapshot above.
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full text-left border-collapse" data-testid="documents-table">
          <thead>
            <tr class="bg-surface-container-low/50 font-sans text-meta font-medium text-on-surface-variant border-b border-outline-variant">
              <th class="py-2.5 pl-lg pr-4">Filename</th>
              <th class="py-2.5 px-4">Type</th>
              <th class="py-2.5 px-4">Target</th>
              <th class="py-2.5 px-4">Size</th>
              <th class="py-2.5 px-4">Status</th>
              <th class="py-2.5 pl-4 pr-lg text-right">Records parsed</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-outline-variant/60 font-sans text-body tabular-nums">
            <tr
              v-for="doc in documents"
              :key="doc.id"
              class="hover:bg-surface-container-low/50 transition-colors duration-150 ease-desk"
              data-testid="document-row"
            >
              <td class="py-3 pl-lg pr-4 font-medium text-on-surface">
                <div class="flex items-center gap-2">
                  <span class="material-symbols-outlined text-[18px] text-outline shrink-0" aria-hidden="true">
                    {{ doc.filename.endsWith('.csv') ? 'table_chart' : 'data_object' }}
                  </span>
                  <span>{{ doc.filename }}</span>
                </div>
              </td>
              <td class="py-3 px-4 text-meta text-on-surface-variant capitalize">
                {{ doc.document_type || doc.account_type || '--' }}
              </td>
              <td class="py-3 px-4 text-meta text-on-surface-variant">
                {{ doc.target_table || 'firestore' }}
              </td>
              <td class="py-3 px-4 text-meta text-on-surface-variant">
                {{ formatBytes(doc.size_bytes) }}
              </td>
              <td class="py-3 px-4">
                <StatusPill :status="doc.status" />
              </td>
              <td class="py-3 pl-4 pr-lg text-right font-semibold text-on-surface">
                {{ doc.records_parsed !== undefined && doc.records_parsed !== null ? doc.records_parsed : '--' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import type { DocumentItem } from '../types';
import { apiService } from '../services/api';
import UploadDropzone from '../components/documents/UploadDropzone.vue';
import StatusPill from '../components/common/StatusPill.vue';

const documents = ref<DocumentItem[]>([]);
const loading = ref(false);
const isUploading = ref(false);
const uploadSuccess = ref<DocumentItem | null>(null);
const uploadError = ref<string | null>(null);

async function loadDocuments() {
  loading.value = true;
  try {
    const list = await apiService.getDocuments();
    documents.value = list || [];
  } catch (err: any) {
    uploadError.value = err?.message ?? 'Failed to load documents';
  } finally {
    loading.value = false;
  }
}

async function onFileSelected(file: File, documentType: string, targetTable?: string) {
  isUploading.value = true;
  uploadError.value = null;
  uploadSuccess.value = null;

  try {
    const docItem = await apiService.uploadDocument(file, documentType, targetTable);
    uploadSuccess.value = docItem;
    await loadDocuments();
  } catch (err: any) {
    uploadError.value = err?.message ?? 'Failed to upload document';
    await loadDocuments();
  } finally {
    isUploading.value = false;
  }
}

function formatBytes(bytes: number): string {
  if (!bytes || bytes === 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

onMounted(() => {
  loadDocuments();
});
</script>
