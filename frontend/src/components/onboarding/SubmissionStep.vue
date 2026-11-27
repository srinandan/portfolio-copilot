<template>
  <div class="flex flex-col gap-lg max-w-2xl mx-auto w-full" data-testid="submission-step">
    <header class="flex flex-col gap-1">
      <h1 class="font-display text-page-title font-medium text-on-surface">Investment Policy Statement (IPS)</h1>
      <p class="font-sans text-body text-on-surface-variant max-w-[65ch]">
        Review your synthesized reference plan before initializing long-term memory and autonomous governance.
      </p>
    </header>

    <!-- Summary Sheet -->
    <section class="bg-surface-container-lowest rounded-xl border border-outline-variant shadow-sheet divide-y divide-outline-variant overflow-hidden">
      <!-- Risk & Horizon -->
      <div class="p-lg grid grid-cols-2 divide-x divide-outline-variant">
        <div class="pr-md">
          <span class="font-sans text-meta text-on-surface-variant block">Risk tolerance</span>
          <span class="font-sans text-heading font-semibold capitalize text-on-surface" data-testid="summary-risk-tier">
            {{ state.risk_tolerance }}
          </span>
        </div>
        <div class="pl-md text-right">
          <span class="font-sans text-meta text-on-surface-variant block">Time horizon</span>
          <span class="font-sans text-heading font-semibold text-on-surface tabular-nums" data-testid="summary-horizon">
            {{ state.time_horizon_years }} Years
          </span>
        </div>
      </div>

      <!-- Primary Goal -->
      <div class="p-lg flex items-baseline justify-between gap-md">
        <div class="flex flex-col">
          <span class="font-sans text-meta text-on-surface-variant">Primary goal</span>
          <span class="font-sans text-body font-medium text-on-surface">
            {{ state.goals[0]?.name || 'Capital Compounding' }}
          </span>
        </div>
        <span class="font-sans text-heading font-semibold text-on-surface tabular-nums shrink-0">
          ${{ (state.goals[0]?.target_amount_usd || 0).toLocaleString() }}
        </span>
      </div>

      <!-- Target Bands Table -->
      <div class="p-lg flex flex-col gap-3">
        <span class="font-sans text-meta font-semibold text-on-surface">Target asset allocation bands</span>
        <div class="border border-outline-variant rounded-md overflow-hidden">
          <div class="bg-surface-container-low/60 px-3 py-2 grid grid-cols-3 font-sans text-meta font-medium text-on-surface-variant">
            <span>Asset class</span>
            <span class="text-center">Target</span>
            <span class="text-right">Tolerance band</span>
          </div>
          <div
            v-for="band in state.target_bands"
            :key="band.asset_class"
            class="px-3 py-2.5 grid grid-cols-3 border-t border-outline-variant/70 items-center font-sans text-body tabular-nums"
            data-testid="summary-band-row"
          >
            <span class="font-medium text-on-surface truncate">{{ band.asset_class }}</span>
            <span class="text-center font-semibold text-on-surface">{{ band.target_percent }}%</span>
            <span class="text-right text-meta text-on-surface-variant">{{ band.min_percent }}%-{{ band.max_percent }}%</span>
          </div>
        </div>
      </div>

      <!-- Liabilities & Guardrails -->
      <div class="p-lg grid grid-cols-1 sm:grid-cols-3 gap-md font-sans tabular-nums">
        <div>
          <span class="text-meta text-on-surface-variant block">Reported liabilities</span>
          <span class="text-body font-semibold text-on-surface">
            ${{ totalLiabilities.toLocaleString() }} ({{ state.liabilities.length }})
          </span>
        </div>
        <div>
          <span class="text-meta text-on-surface-variant block">Concentration limit</span>
          <span class="text-body font-semibold text-on-surface">
            {{ state.constraints.concentration_limit_percent }}% max / position
          </span>
        </div>
        <div>
          <span class="text-meta text-on-surface-variant block">Approval threshold</span>
          <span class="text-body font-semibold text-on-surface">
            &gt; ${{ state.approval_thresholds.approval_required_above_usd.toLocaleString() }} ({{ state.approval_thresholds.approval_required_above_percent }}%)
          </span>
        </div>
      </div>
    </section>

    <!-- Submission Status Banner -->
    <div
      v-if="submitting || submissionSuccess || submissionError"
      class="p-md rounded-xl border flex flex-col gap-1.5"
      :class="[
        submissionSuccess ? 'bg-tertiary-fixed/50 border-tertiary-fixed-dim text-on-tertiary-fixed' :
        submissionError ? 'bg-error-container text-on-error-container border-error/30' :
        'bg-surface-container-lowest border-outline-variant text-on-surface'
      ]"
      data-testid="submission-status-banner"
    >
      <div class="flex items-center gap-2">
        <span
          v-if="submitting"
          class="material-symbols-outlined animate-spin text-[20px] text-primary-fixed"
          aria-hidden="true"
        >
          progress_activity
        </span>
        <span
          v-else-if="submissionSuccess"
          class="material-symbols-outlined text-[20px] text-on-tertiary-container"
          aria-hidden="true"
        >
          check_circle
        </span>
        <span
          v-else
          class="material-symbols-outlined text-[20px] text-error"
          aria-hidden="true"
        >
          error
        </span>
        <span class="font-sans text-body font-semibold">
          {{
            submitting ? 'Initializing Active IPS...' :
            submissionSuccess ? 'Active IPS initialized and governance online' :
            'Submission notice'
          }}
        </span>
      </div>
      <p class="font-sans text-meta max-w-[65ch]">
        {{
          submitting ? 'Writing InvestmentPolicyStatement and LiabilitiesSnapshot to Firestore.' :
          submissionSuccess ? 'Your policy reference plan is now active. All portfolio reviews, drift checks, and proposed actions validate against this IPS.' :
          submissionError
        }}
      </p>
    </div>

    <!-- Primary CTA -->
    <div>
      <button
        v-if="!submissionSuccess"
        type="button"
        class="w-full bg-primary text-on-primary py-3.5 px-lg rounded-md font-sans text-body font-medium inline-flex items-center justify-center gap-2 transition-colors duration-200 ease-desk hover:bg-primary-container disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="submitting"
        data-testid="submit-ips-btn"
        @click="handleSubmit"
      >
        <span v-if="!submitting">Submit Policy &amp; Initialize Governance</span>
        <span v-else>Saving policy...</span>
        <span v-if="!submitting" class="material-symbols-outlined text-[18px]" aria-hidden="true">send</span>
      </button>

      <button
        v-else
        type="button"
        class="w-full bg-tertiary text-on-tertiary py-3.5 px-lg rounded-md font-sans text-body font-medium inline-flex items-center justify-center gap-2 transition-colors duration-200 ease-desk hover:bg-on-tertiary-fixed"
        data-testid="go-to-dashboard-btn"
        @click="navigateToDashboard"
      >
        <span>Enter Portfolio Dashboard</span>
        <span class="material-symbols-outlined text-[18px]" aria-hidden="true">dashboard</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import type { OnboardingState } from '../../types';
import { apiService } from '../../services/api';

const props = withDefaults(
  defineProps<{
    state: OnboardingState;
    isUpdate?: boolean;
  }>(),
  {
    isUpdate: false
  }
);

const emit = defineEmits<{
  (e: 'complete'): void;
}>();

const router = useRouter();
const submitting = ref(false);
const submissionSuccess = ref(false);
const submissionError = ref<string | null>(null);

const totalLiabilities = computed(() => {
  return props.state.liabilities.reduce((acc, l) => acc + (Number(l.balance_usd) || 0), 0);
});

async function handleSubmit() {
  submitting.value = true;
  submissionError.value = null;

  const s = props.state;
  const userId = s.user_id || 'demo_user';
  const [primaryGoal, ...additionalGoals] = s.goals;

  const result: Record<string, unknown> = {
    user_id: userId,
    primary_goal: primaryGoal ?? null,
    additional_goals: additionalGoals ?? [],
    risk_tolerance: s.risk_tolerance,
    time_horizon_years: s.time_horizon_years,
    target_allocation: s.target_bands,
    constraints: {
      excluded_tickers: s.constraints.excluded_tickers ?? [],
      excluded_sectors: s.constraints.excluded_sectors ?? [],
      concentration_limit_percent: s.constraints.concentration_limit_percent,
      tax_loss_harvesting_enabled: s.constraints.tax_loss_harvesting_enabled ?? false,
      account_type: s.constraints.account_type
    },
    liquidity_needs: {
      reserve_months: s.reserve_months,
      known_upcoming_expenses_usd: s.known_upcoming_expenses_usd
    },
    identified_liabilities: s.liabilities.map(l => ({
      liability_id: l.liability_id,
      type: l.type,
      description: l.description,
      balance_usd: Number(l.balance_usd) || 0,
      interest_rate_percent: Number(l.interest_rate_percent) || 0,
      minimum_payment_usd: Number(l.minimum_payment_usd) || 0
    })),
    interview_summary: `Wizard onboarding: ${s.risk_tolerance} risk, ${s.time_horizon_years}y horizon, ${s.liabilities.length} liabilities.`
  };

  try {
    await apiService.applyOnboarding({
      user_id: userId,
      result,
      trigger: props.isUpdate ? 'update' : 'initial',
      approval_required_above_usd: s.approval_thresholds.approval_required_above_usd,
      approval_required_above_percent: s.approval_thresholds.approval_required_above_percent
    });
    submissionSuccess.value = true;
  } catch (err: any) {
    submissionError.value = err?.message ?? String(err);
  } finally {
    submitting.value = false;
  }
}

function navigateToDashboard() {
  emit('complete');
  router.push('/');
}
</script>
