<template>
  <div class="flex flex-col lg:flex-row gap-lg lg:gap-xl w-full">
    <!-- Left Column: Upload Area & Sources -->
    <div class="flex flex-col gap-lg lg:w-[40%] lg:flex-shrink-0">
      <UploadDropzone @file-selected="onFileSelected" />

      <!-- Supported Sources -->
      <section class="bg-surface-container-lowest rounded-xl shadow-sm border border-surface-variant">
        <div class="p-md border-b border-surface-variant">
          <h2 class="font-title-sm text-title-sm text-on-surface">Recognized Formats</h2>
        </div>
        <div class="p-md grid grid-cols-2 gap-sm">
          <div class="bg-surface-container flex items-center gap-sm p-sm rounded-md border border-surface-variant">
            <div class="w-6 h-6 rounded-full bg-secondary-fixed flex items-center justify-center text-on-secondary-fixed font-title-sm text-[12px]">CS</div>
            <span class="font-body-mono text-body-mono text-on-surface truncate">Charles Schwab</span>
          </div>
          <div class="bg-surface-container flex items-center gap-sm p-sm rounded-md border border-surface-variant">
            <div class="w-6 h-6 rounded-full bg-tertiary-fixed flex items-center justify-center text-on-tertiary-fixed font-title-sm text-[12px]">F</div>
            <span class="font-body-mono text-body-mono text-on-surface truncate">Fidelity</span>
          </div>
          <div class="bg-surface-container flex items-center gap-sm p-sm rounded-md border border-surface-variant">
            <div class="w-6 h-6 rounded-full bg-primary-fixed flex items-center justify-center text-on-primary-fixed font-title-sm text-[12px]">VG</div>
            <span class="font-body-mono text-body-mono text-on-surface truncate">Vanguard</span>
          </div>
          <div class="bg-surface-container flex items-center gap-sm p-sm rounded-md border border-surface-variant">
            <div class="w-6 h-6 rounded-full bg-surface-variant flex items-center justify-center text-on-surface-variant font-title-sm text-[12px]">IB</div>
            <span class="font-body-mono text-body-mono text-on-surface truncate">Interactive Brokers</span>
          </div>
        </div>
      </section>
    </div>

    <!-- Right Column: Processing History -->
    <div class="flex flex-col flex-1 bg-surface-container-lowest rounded-xl shadow-sm border border-surface-variant">
      <div class="p-md border-b border-surface-variant flex items-center justify-between bg-surface-container-lowest sticky top-0 z-10">
        <h2 class="font-title-sm text-title-sm text-on-surface">Processing Log</h2>
        <button
          class="text-primary font-label-caps text-label-caps hover:bg-surface-container p-xs rounded transition-colors uppercase"
          @click="clearLog"
        >
          CLEAR ALL
        </button>
      </div>
      <div class="p-md flex flex-col gap-sm">
        <div
          v-for="doc in documents"
          :key="doc.id"
          class="border border-surface-variant rounded-lg p-md flex flex-col sm:flex-row sm:items-center justify-between gap-md hover:bg-surface-container-low transition-colors group"
          data-testid="doc-item"
        >
          <div class="flex items-start gap-md">
            <div class="w-10 h-10 rounded-full bg-tertiary-fixed-dim flex items-center justify-center flex-shrink-0">
              <span class="material-symbols-outlined text-on-tertiary-fixed">description</span>
            </div>
            <div>
              <h4 class="font-body-mono text-body-mono text-on-surface">{{ doc.filename }}</h4>
              <div class="flex items-center gap-sm mt-xs">
                <span class="font-label-caps text-label-caps text-on-surface-variant">{{ formatSize(doc.size_bytes) }}</span>
                <span class="w-1 h-1 rounded-full bg-outline-variant"></span>
                <span class="font-label-caps text-label-caps text-on-surface-variant">{{ doc.uploaded_at }}</span>
              </div>
            </div>
          </div>
          <div class="flex items-center justify-between sm:justify-end gap-md">
            <StatusPill :status="doc.status" :label="doc.status === 'SUCCESS' ? 'VERIFIED' : doc.status" />
            <span v-if="doc.records_parsed" class="font-body-mono text-xs text-on-surface-variant">
              {{ doc.records_parsed }} records
            </span>
          </div>
        </div>
        <div v-if="documents.length === 0" class="p-lg text-center text-on-surface-variant font-body-base">
          No documents uploaded yet.
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import type { DocumentItem } from '../types';
import { gatewayService } from '../services/gateway';
import UploadDropzone from '../components/documents/UploadDropzone.vue';
import StatusPill from '../components/common/StatusPill.vue';

const documents = ref<DocumentItem[]>([]);

onMounted(async () => {
  try {
    const data = await gatewayService.getDocuments();
    documents.value = data;
  } catch {
    // Empty default
  }
});

function onFileSelected(file: File) {
  documents.value.unshift({
    id: `doc-${Date.now()}`,
    filename: file.name,
    size_bytes: file.size,
    uploaded_at: 'JUST NOW',
    status: 'SUCCESS',
    records_parsed: 15
  });
}

function clearLog() {
  documents.value = [];
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
</script>
