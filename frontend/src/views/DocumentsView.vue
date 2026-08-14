<template>
  <div class="flex flex-col gap-xl max-w-6xl mx-auto w-full pb-16" data-testid="documents-view">
    <!-- Header -->
    <div class="flex flex-col gap-xs">
      <div class="flex items-center gap-xs text-on-surface-variant font-label-caps uppercase tracking-wider text-xs">
        <span class="material-symbols-outlined text-[16px] text-tertiary-fixed-dim">folder_managed</span>
        <span>Data Pipeline</span>
      </div>
      <h1 class="font-headline-lg-mobile md:font-headline-lg text-on-surface">Documents &amp; File Ingestion</h1>
      <p class="font-body-base text-on-surface-variant text-sm max-w-2xl">
        Upload bank transactions (CSV) or balance/IPS snapshots (JSON). All uploaded files undergo strict schema validation and are committed directly to BigQuery or Firestore.
      </p>
    </div>

    <!-- Upload Status Alerts -->
    <div
      v-if="uploadSuccess"
      class="bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-300 text-emerald-900 dark:text-emerald-200 p-md rounded-xl flex items-center justify-between shadow-sm"
      data-testid="upload-success-alert"
    >
      <div class="flex items-center gap-sm">
        <span class="material-symbols-outlined text-emerald-600 dark:text-emerald-400">check_circle</span>
        <div class="text-sm font-body-base">
          <span class="font-bold">Ingestion Successful:</span>
          Parsed <span class="font-mono font-bold">{{ uploadSuccess.records_parsed ?? 0 }}</span> records from <span class="font-mono">{{ uploadSuccess.filename }}</span> into {{ uploadSuccess.target_table || uploadSuccess.document_type || uploadSuccess.account_type }}.
        </div>
      </div>
      <button class="text-xs uppercase font-label-caps hover:underline opacity-80" @click="uploadSuccess = null">Dismiss</button>
    </div>

    <div
      v-if="uploadError"
      class="bg-error-container text-on-error-container border border-error p-md rounded-xl flex items-center justify-between shadow-sm"
      data-testid="upload-error-alert"
    >
      <div class="flex items-center gap-sm">
        <span class="material-symbols-outlined">error</span>
        <div class="text-sm font-body-base">
          <span class="font-bold">Upload Failed:</span> {{ uploadError }}
        </div>
      </div>
      <button class="text-xs uppercase font-label-caps hover:underline opacity-80" @click="uploadError = null">Dismiss</button>
    </div>

    <!-- Dropzone Area -->
    <UploadDropzone
      :uploading="isUploading"
      @file-selected="onFileSelected"
    />

    <!-- Document History Table -->
    <section class="bg-surface-container-lowest rounded-xl border border-surface-variant shadow-sm overflow-hidden flex flex-col">
      <div class="p-md border-b border-surface-variant flex items-center justify-between">
        <div class="flex items-center gap-sm">
          <span class="material-symbols-outlined text-outline">history</span>
          <h2 class="font-title-sm text-title-sm text-on-surface">Ingested Documents History</h2>
        </div>
        <button
          class="text-xs flex items-center gap-xs font-label-caps uppercase text-primary hover:bg-surface-container px-sm py-xs rounded-md transition-colors"
          data-testid="refresh-documents-btn"
          @click="loadDocuments"
        >
          <span class="material-symbols-outlined text-[16px]">refresh</span>
          Refresh
        </button>
      </div>

      <div v-if="loading" class="p-xl text-center text-on-surface-variant font-body-base">
        Loading documents...
      </div>

      <div v-else-if="documents.length === 0" class="p-xl text-center text-on-surface-variant font-body-base">
        No documents uploaded yet. Upload a statement or snapshot above.
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full text-left text-sm" data-testid="documents-table">
          <thead class="bg-surface-container text-xs font-label-caps uppercase text-on-surface-variant border-b border-surface-variant">
            <tr>
              <th class="py-sm px-md">Filename</th>
              <th class="py-sm px-md">Type</th>
              <th class="py-sm px-md">Target</th>
              <th class="py-sm px-md">Size</th>
              <th class="py-sm px-md">Status</th>
              <th class="py-sm px-md text-right">Records Parsed</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-surface-variant/40 font-body-base">
            <tr
              v-for="doc in documents"
              :key="doc.id"
              class="hover:bg-surface-container-low transition-colors"
              data-testid="document-row"
            >
              <td class="py-sm px-md font-medium text-on-surface">
                <div class="flex items-center gap-xs">
                  <span class="material-symbols-outlined text-[18px] text-on-surface-variant">
                    {{ doc.filename.endsWith('.csv') ? 'table_chart' : 'data_object' }}
                  </span>
                  <span>{{ doc.filename }}</span>
                </div>
              </td>
              <td class="py-sm px-md uppercase text-xs font-mono text-on-surface-variant">
                {{ doc.document_type || doc.account_type }}
              </td>
              <td class="py-sm px-md font-mono text-xs text-on-surface-variant">
                {{ doc.target_table || 'firestore' }}
              </td>
              <td class="py-sm px-md text-xs font-mono text-on-surface-variant">
                {{ formatBytes(doc.size_bytes) }}
              </td>
              <td class="py-sm px-md">
                <span
                  class="px-2 py-0.5 rounded-full text-xs font-bold font-mono inline-block"
                  :class="[
                    doc.status === 'SUCCESS'
                      ? 'bg-emerald-100 dark:bg-emerald-950/50 text-emerald-800 dark:text-emerald-300'
                      : doc.status === 'FAILED'
                      ? 'bg-rose-100 dark:bg-rose-950/50 text-rose-800 dark:text-rose-300'
                      : 'bg-amber-100 dark:bg-amber-950/50 text-amber-800 dark:text-amber-300'
                  ]"
                >
                  {{ doc.status }}
                </span>
              </td>
              <td class="py-sm px-md text-right font-mono font-bold text-on-surface">
                {{ doc.records_parsed !== undefined && doc.records_parsed !== null ? doc.records_parsed : '—' }}
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
