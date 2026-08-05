<template>
  <section class="bg-surface-container-lowest rounded-xl shadow-sm border border-surface-variant flex flex-col">
    <div class="p-md border-b border-surface-variant flex items-center justify-between">
      <h2 class="font-headline-md text-headline-md text-on-surface">Secure Upload</h2>
      <span class="material-symbols-outlined text-outline">verified_user</span>
    </div>
    <div class="p-lg">
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
          accept=".csv,.pdf"
          data-testid="file-input"
          @change="onFileSelect"
        />
        <img alt="Upload Statement Icon" class="w-16 h-16 object-contain mb-md opacity-80" src="/images/upload_icon.png" />
        <h3 class="font-title-sm text-title-sm text-on-surface mb-xs">
          {{ selectedFile ? selectedFile.name : 'Drop Statements Here' }}
        </h3>
        <p class="font-body-base text-body-base text-on-surface-variant mb-md max-w-[240px]">
          {{ selectedFile ? `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB • Ready to process` : 'CSV or PDF format. End-of-month statements preferred.' }}
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
          <span class="font-semibold text-on-surface">Privacy First:</span> We never connect directly to your bank. All data is processed locally from your uploaded files.
        </p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const emit = defineEmits<{
  (e: 'file-selected', file: File): void;
}>();

const isDragging = ref(false);
const selectedFile = ref<File | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);

function triggerFileInput() {
  fileInputRef.value?.click();
}

function handleFile(file: File) {
  selectedFile.value = file;
  emit('file-selected', file);
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
