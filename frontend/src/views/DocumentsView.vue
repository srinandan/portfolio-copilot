<template>
  <div class="flex flex-col items-center justify-center py-xl gap-md text-center max-w-2xl mx-auto" data-testid="documents-view">
    <div class="w-14 h-14 rounded-full bg-surface-container flex items-center justify-center">
      <span class="material-symbols-outlined text-outline text-[28px]">description</span>
    </div>
    <h2 class="font-title-sm text-title-sm text-on-surface">Statement upload — coming soon</h2>
    <p class="font-body-base text-body-base text-on-surface-variant text-sm max-w-md">
      This will accept CSV and PDF brokerage statements, parse them locally,
      and use the results to update your holdings snapshot. It isn't wired
      to a parser or storage yet, so the upload has been disabled to avoid
      showing fake "processed" statements.
    </p>
    <p class="font-body-mono text-xs text-on-surface-variant">
      Tracking: v0.2 — see the project roadmap for status.
    </p>
    <a
      href="/"
      class="mt-sm inline-flex items-center gap-xs text-primary hover:underline font-label-caps text-label-caps uppercase"
      data-testid="documents-back-to-dashboard"
    >
      <span class="material-symbols-outlined text-[16px]">arrow_back</span>
      Back to Dashboard
    </a>
  </div>
</template>

<script setup lang="ts">
// This view intentionally has no logic. The previous implementation faked an
// upload → parse → success flow with hardcoded records_parsed: 15. Removed
// per the second-pass review (finding B). Reintroduce when a real POST
// /api/documents backend path with a parser lands.
</script>
