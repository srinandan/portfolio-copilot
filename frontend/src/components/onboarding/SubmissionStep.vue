<template>
  <div class="flex flex-col gap-lg max-w-2xl mx-auto w-full" data-testid="submission-step">
    <!-- Header -->
    <div class="flex flex-col gap-sm">
      <div class="flex items-center gap-xs text-on-surface-variant font-label-caps uppercase tracking-wider">
        <span class="material-symbols-outlined text-[16px] text-tertiary-fixed-dim">verified</span>
        <span>Final Review &amp; Initialization</span>
      </div>
      <h1 class="font-headline-lg-mobile text-on-surface">Investment Policy Statement (IPS)</h1>
      <p class="font-body-base text-on-surface-variant">
        Review your synthesized reference plan before initializing long-term memory and autonomous governance.
      </p>
    </div>

    <!-- Summary Bento Card -->
    <div class="bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sm flex flex-col gap-md">
      <!-- Risk Tier & Horizon -->
      <div class="flex justify-between items-center border-b border-outline-variant/40 pb-sm">
        <div>
          <span class="font-label-caps text-xs text-on-surface-variant uppercase">Risk Tolerance</span>
          <div class="font-title-sm text-on-surface capitalize font-bold text-lg" data-testid="summary-risk-tier">
            {{ state.risk_tolerance }}
          </div>
        </div>
        <div class="text-right">
          <span class="font-label-caps text-xs text-on-surface-variant uppercase">Time Horizon</span>
          <div class="font-title-sm text-on-surface font-mono" data-testid="summary-horizon">
            {{ state.time_horizon_years }} Years
          </div>
        </div>
      </div>

      <!-- Primary Goal -->
      <div class="flex flex-col gap-xs">
        <span class="font-label-caps text-xs text-on-surface-variant uppercase">Primary Goal</span>
        <div class="flex justify-between items-center text-sm font-body-base bg-surface-container p-sm rounded-lg">
          <span class="font-medium text-on-surface">{{ state.goals[0]?.name || 'Capital Compounding' }}</span>
          <span class="font-body-mono font-bold text-on-surface">${{ (state.goals[0]?.target_amount_usd || 0).toLocaleString() }}</span>
        </div>
      </div>

      <!-- Target Bands Table -->
      <div class="flex flex-col gap-xs">
        <span class="font-label-caps text-xs text-on-surface-variant uppercase">Target Asset Allocation Bands</span>
        <div class="border border-outline-variant rounded-lg overflow-hidden text-xs">
          <div class="bg-surface-container-high p-2 grid grid-cols-3 font-label-caps text-on-surface-variant uppercase">
            <span>Asset Class</span>
            <span class="text-center">Target</span>
            <span class="text-right">Tolerance Band</span>
          </div>
          <div
            v-for="band in state.target_bands"
            :key="band.asset_class"
            class="p-2 grid grid-cols-3 border-t border-outline-variant/40 items-center font-body-mono"
            data-testid="summary-band-row"
          >
            <span class="font-body-base text-xs text-on-surface font-medium truncate">{{ band.asset_class }}</span>
            <span class="text-center font-bold text-on-surface">{{ band.target_percent }}%</span>
            <span class="text-right text-on-surface-variant">{{ band.min_percent }}% – {{ band.max_percent }}%</span>
          </div>
        </div>
      </div>

      <!-- Liabilities Summary -->
      <div class="flex flex-col gap-xs pt-sm border-t border-outline-variant/40">
        <div class="flex justify-between items-center">
          <span class="font-label-caps text-xs text-on-surface-variant uppercase">Reported Liabilities</span>
          <span class="font-body-mono text-xs text-on-surface font-bold">
            ${{ totalLiabilities.toLocaleString() }} ({{ state.liabilities.length }} debts)
          </span>
        </div>
      </div>

      <!-- Policy Guardrails Summary -->
      <div class="grid grid-cols-2 gap-md pt-sm border-t border-outline-variant/40 text-xs font-body-mono">
        <div>
          <span class="text-on-surface-variant block">Concentration Limit:</span>
          <span class="font-bold text-on-surface">{{ state.constraints.concentration_limit_percent }}% max / position</span>
        </div>
        <div>
          <span class="text-on-surface-variant block">Approval Threshold:</span>
          <span class="font-bold text-on-surface">&gt; ${{ state.approval_thresholds.approval_required_above_usd.toLocaleString() }} ({{ state.approval_thresholds.approval_required_above_percent }}%)</span>
        </div>
      </div>
    </div>

    <!-- Submission / SSE Stream State -->
    <div
      v-if="submitting || submissionSuccess || submissionError"
      class="p-md rounded-xl border flex flex-col gap-sm shadow-sm"
      :class="[
        submissionSuccess ? 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-300 text-emerald-900 dark:text-emerald-200' :
        submissionError ? 'bg-error-container text-on-error-container border-error' :
        'bg-surface-container border-outline-variant text-on-surface'
      ]"
      data-testid="submission-status-banner"
    >
      <div class="flex items-center gap-2">
        <span
          v-if="submitting"
          class="material-symbols-outlined animate-spin text-[20px] text-primary"
        >
          progress_activity
        </span>
        <span
          v-else-if="submissionSuccess"
          class="material-symbols-outlined text-[20px] text-emerald-600"
        >
          check_circle
        </span>
        <span
          v-else
          class="material-symbols-outlined text-[20px] text-error"
        >
          error
        </span>
        <span class="font-title-sm text-sm">
          {{
            submitting ? 'Initializing Active IPS with Agent Runtime...' :
            submissionSuccess ? 'Active IPS Initialized & Governance Online!' :
            'Submission Notice'
          }}
        </span>
      </div>
      <p class="font-body-base text-xs">
        {{
          submitting ? 'Writing InvestmentPolicyStatement v1 and LiabilitiesSnapshot to long-term memory via /api/plan SSE bridge.' :
          submissionSuccess ? 'Your policy reference plan is now active. All subsequent portfolio reviews, drift scans, and proposed actions will validate against this IPS.' :
          submissionError
        }}
      </p>
    </div>

    <!-- CTA Button -->
    <div class="mt-md flex flex-col gap-sm">
      <button
        v-if="!submissionSuccess"
        class="w-full bg-primary-container text-on-primary py-md px-lg rounded-lg font-title-sm flex items-center justify-center gap-sm transition-colors shadow-md hover:bg-primary-container/90 disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="submitting"
        data-testid="submit-ips-btn"
        @click="handleSubmit"
      >
        <span v-if="!submitting">Submit Policy &amp; Initialize Governance</span>
        <span v-else>Communicating with Orchestrator...</span>
        <span v-if="!submitting" class="material-symbols-outlined">send</span>
      </button>

      <button
        v-else
        class="w-full bg-tertiary-container text-on-tertiary-container py-md px-lg rounded-lg font-title-sm flex items-center justify-center gap-sm transition-colors shadow-md hover:opacity-90"
        data-testid="go-to-dashboard-btn"
        @click="navigateToDashboard"
      >
        <span>Enter Portfolio Dashboard</span>
        <span class="material-symbols-outlined">dashboard</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import type { OnboardingState } from '../../types';
import { apiService } from '../../services/api';

const props = defineProps<{
  state: OnboardingState;
}>();

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

  // Map the wizard's typed state to the orchestrator's GoalsOnboardingResult contract.
  // Structured all the way — no LLM re-parsing of prose.
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
      account_type: s.constraints.account_type === 'taxable' || s.constraints.account_type === 'retirement'
        ? s.constraints.account_type
        : undefined
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
      trigger: 'initial',
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
