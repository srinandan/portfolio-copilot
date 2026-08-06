<template>
  <div class="flex flex-col gap-lg max-w-2xl mx-auto w-full" data-testid="statement-upload-step">
    <!-- Header -->
    <div class="flex flex-col gap-sm">
      <div class="flex items-center gap-xs text-on-surface-variant font-label-caps uppercase tracking-wider">
        <span class="material-symbols-outlined text-[16px] text-tertiary-fixed-dim">verified</span>
        <span>Profile Complete</span>
      </div>
      <h1 class="font-headline-lg-mobile text-on-surface">Ready to begin analysis.</h1>
      <p class="font-body-base text-on-surface-variant">
        Upload your first brokerage statement to establish your baseline. All processing happens locally on your device.
      </p>
    </div>

    <!-- Dropzone Area -->
    <div class="flex flex-col justify-center">
      <label
        v-if="!selectedFile"
        class="relative group cursor-pointer w-full aspect-[4/3] rounded-xl bg-surface-container-low flex flex-col items-center justify-center gap-md border border-dashed border-outline-variant transition-all hover:bg-surface-container hover:border-tertiary-fixed-dim overflow-hidden shadow-sm"
        for="onboarding-upload"
        data-testid="onboarding-dropzone"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="onDrop"
      >
        <div
          class="absolute inset-0 bg-tertiary-fixed-dim/10 pointer-events-none transition-opacity duration-300"
          :class="isDragging ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'"
        ></div>
        <div class="w-16 h-16 rounded-full bg-surface-container flex items-center justify-center text-on-surface-variant group-hover:text-tertiary-fixed-dim group-hover:bg-surface transition-colors duration-300 z-10 shadow-sm">
          <span class="material-symbols-outlined text-[32px]">upload_file</span>
        </div>
        <div class="text-center z-10 px-lg">
          <span class="block font-title-sm text-on-surface mb-xs">Browse Statements</span>
          <span class="block font-body-mono text-[12px] text-on-surface-variant">PDF, CSV up to 10MB</span>
        </div>
        <div class="absolute bottom-4 left-0 w-full flex justify-center z-10">
          <div class="flex items-center gap-xs px-sm py-xs rounded-full bg-surface-container text-on-surface-variant">
            <span class="material-symbols-outlined text-[14px]" style="font-variation-settings: 'FILL' 1;">lock</span>
            <span class="font-body-mono text-[10px]">Locally Encrypted</span>
          </div>
        </div>
        <input
          id="onboarding-upload"
          type="file"
          accept=".pdf,.csv"
          class="hidden"
          data-testid="onboarding-file-input"
          @change="onFileSelected"
        />
      </label>

      <!-- Uploaded File Status Card -->
      <div
        v-else
        class="w-full bg-surface-container-low rounded-lg p-md border border-outline-variant shadow-sm flex flex-col gap-md"
        data-testid="uploaded-file-card"
      >
        <div class="flex items-start gap-md">
          <div class="w-10 h-10 rounded bg-surface flex items-center justify-center flex-shrink-0 border border-outline-variant">
            <span class="material-symbols-outlined text-tertiary-fixed-dim">description</span>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex justify-between items-start mb-xs">
              <span class="font-body-base font-semibold text-on-surface truncate pr-sm" data-testid="file-name">
                {{ selectedFile.name }}
              </span>
              <button
                class="text-on-surface-variant hover:text-error transition-colors"
                data-testid="remove-file-btn"
                @click="removeFile"
              >
                <span class="material-symbols-outlined text-[18px]">close</span>
              </button>
            </div>
            <div class="flex justify-between items-center">
              <span class="font-body-mono text-[11px] text-on-surface-variant" data-testid="file-size">
                {{ formatSize(selectedFile.size_bytes) }}
              </span>
              <span class="font-label-caps text-on-tertiary-container bg-tertiary-fixed-dim/20 px-2 py-0.5 rounded text-[11px]">
                PARSED: {{ selectedFile.records_parsed }} ROWS
              </span>
            </div>
          </div>
        </div>
        <div class="pt-sm border-t border-outline-variant/30 flex items-center justify-between">
          <div class="flex items-center gap-xs text-on-tertiary-container">
            <span class="material-symbols-outlined text-[14px]">shield_lock</span>
            <span class="font-body-mono text-[11px]">Secure Processing Active</span>
          </div>
          <span class="material-symbols-outlined text-on-tertiary-container text-[16px]">check_circle</span>
        </div>
      </div>
    </div>

    <!-- CTA -->
    <div class="mt-md">
      <button
        class="w-full font-title-sm py-4 rounded-lg flex items-center justify-center gap-sm transition-all shadow-sm"
        :class="[
          selectedFile
            ? 'bg-primary-container text-on-primary hover:bg-primary-container/90'
            : 'bg-surface-container text-on-surface-variant opacity-50 cursor-not-allowed'
        ]"
        :disabled="!selectedFile"
        data-testid="begin-analysis-btn"
        @click="$emit('complete', selectedFile)"
      >
        <span>Begin Analysis</span>
        <span class="material-symbols-outlined text-[20px]">arrow_forward</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

interface UploadedFileInfo {
  name: string;
  size_bytes: number;
  records_parsed: number;
}

defineEmits<{
  (e: 'complete', file: UploadedFileInfo | null): void;
}>();

const selectedFile = ref<UploadedFileInfo | null>(null);
const isDragging = ref(false);

function formatSize(bytes: number): string {
  if (!bytes) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function handleFile(file: File) {
  selectedFile.value = {
    name: file.name,
    size_bytes: file.size,
    records_parsed: Math.floor(Math.random() * 50) + 120 // simulated parsed count
  };
}

function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  if (input.files && input.files[0]) {
    handleFile(input.files[0]);
  }
}

function onDrop(event: DragEvent) {
  isDragging.value = false;
  if (event.dataTransfer && event.dataTransfer.files.length > 0) {
    handleFile(event.dataTransfer.files[0]);
  }
}

function removeFile() {
  selectedFile.value = null;
}
</script>
