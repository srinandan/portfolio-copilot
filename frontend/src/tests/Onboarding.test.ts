import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, fireEvent, screen, cleanup } from '@testing-library/vue';
import { deriveRiskTolerance, getDefaultAllocationBands } from '../services/onboarding';
import { apiService } from '../services/api';

import WelcomeStep from '../components/onboarding/WelcomeStep.vue';
import GoalsStep from '../components/onboarding/GoalsStep.vue';
import LiabilitiesStep from '../components/onboarding/LiabilitiesStep.vue';
import RiskCalibrationStep from '../components/onboarding/RiskCalibrationStep.vue';
import TargetAllocationStep from '../components/onboarding/TargetAllocationStep.vue';
import ConstraintsStep from '../components/onboarding/ConstraintsStep.vue';
import SubmissionStep from '../components/onboarding/SubmissionStep.vue';
import OnboardingView from '../views/OnboardingView.vue';

const mockPush = vi.fn();
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush
  })
}));

describe('Goals & Onboarding Interview (Issue #28 / S1)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  describe('Deterministic Risk Tolerance Derivation (SKILL.md §Risk tolerance)', () => {
    it('maps >= 15 years with hold/buy_more to aggressive', () => {
      expect(deriveRiskTolerance(15, 'hold')).toBe('aggressive');
      expect(deriveRiskTolerance(20, 'buy_more')).toBe('aggressive');
    });

    it('maps >= 7 years with hold/buy_more to moderate', () => {
      expect(deriveRiskTolerance(7, 'hold')).toBe('moderate');
      expect(deriveRiskTolerance(10, 'buy_more')).toBe('moderate');
    });

    it('maps any horizon with sell reaction to conservative', () => {
      expect(deriveRiskTolerance(30, 'sell')).toBe('conservative');
      expect(deriveRiskTolerance(10, 'sell')).toBe('conservative');
      expect(deriveRiskTolerance(3, 'sell')).toBe('conservative');
    });

    it('maps < 7 years with hold/buy_more to moderate', () => {
      expect(deriveRiskTolerance(5, 'hold')).toBe('moderate');
      expect(deriveRiskTolerance(2, 'buy_more')).toBe('moderate');
    });

    it('returns valid default allocation bands for all tiers', () => {
      const cons = getDefaultAllocationBands('conservative');
      expect(cons[0].target_percent).toBe(30);
      expect(cons[0].min_percent).toBe(20);
      expect(cons[0].max_percent).toBe(40);

      const mod = getDefaultAllocationBands('moderate');
      expect(mod[0].target_percent).toBe(60);
      expect(mod[0].min_percent).toBe(50);
      expect(mod[0].max_percent).toBe(70);

      const agg = getDefaultAllocationBands('aggressive');
      expect(agg[0].target_percent).toBe(85);
      expect(agg[0].min_percent).toBe(75);
      expect(agg[0].max_percent).toBe(95);
    });
  });

  describe('WelcomeStep.vue', () => {
    it('renders hero and emits next when Start Setup is clicked', async () => {
      const { emitted } = render(WelcomeStep);
      expect(screen.getByText('Welcome to Portfolio Copilot')).toBeDefined();
      expect(screen.getByText('Security through Privacy')).toBeDefined();

      const startBtn = screen.getByTestId('start-setup-btn');
      await fireEvent.click(startBtn);
      expect(emitted().next).toBeTruthy();
    });
  });

  describe('Turn 1: GoalsStep.vue', () => {
    it('collects goal name, target amount, target date, horizon, and near-term expenses', async () => {
      const { emitted } = render(GoalsStep);

      const nameInput = screen.getByTestId('input-goal-name');
      const amountInput = screen.getByTestId('input-target-amount');
      const expensesInput = screen.getByTestId('input-upcoming-expenses');

      await fireEvent.update(nameInput, 'Retirement Nest Egg');
      await fireEvent.update(amountInput, '2000000');
      await fireEvent.update(expensesInput, '25000');

      const confirmBtn = screen.getByTestId('confirm-goals-btn');
      await fireEvent.click(confirmBtn);

      expect(emitted().next).toBeTruthy();
      const payload = (emitted().next as any)[0][0];
      expect(payload.goals[0].name).toBe('Retirement Nest Egg');
      expect(payload.goals[0].target_amount_usd).toBe(2000000);
      expect(payload.knownUpcomingExpensesUsd).toBe(25000);
      expect(payload.timeHorizonYears).toBeGreaterThan(0);
    });
  });

  describe('Turn 2: LiabilitiesStep.vue', () => {
    it('captures debts, displays total liabilities, and handles zero debt toggle', async () => {
      const { emitted } = render(LiabilitiesStep);

      expect(screen.getByTestId('total-liabilities-display')).toBeDefined();

      // Add another liability
      const addBtn = screen.getByTestId('add-liability-btn');
      await fireEvent.click(addBtn);

      const balanceInputs = screen.getAllByTestId('input-liability-balance');
      expect(balanceInputs.length).toBeGreaterThan(1);

      const confirmBtn = screen.getByTestId('confirm-liabilities-btn');
      await fireEvent.click(confirmBtn);

      expect(emitted().next).toBeTruthy();
    });

    it('submits empty liabilities array when no debt toggle is checked', async () => {
      const { emitted } = render(LiabilitiesStep);

      const noDebtToggle = screen.getByTestId('no-debt-toggle');
      await fireEvent.click(noDebtToggle);

      const confirmBtn = screen.getByTestId('confirm-liabilities-btn');
      await fireEvent.click(confirmBtn);

      expect(emitted().next).toBeTruthy();
      expect((emitted().next as any)[0][0]).toEqual([]);
    });
  });

  describe('Turn 3: RiskCalibrationStep.vue', () => {
    it('dynamically calibrates risk tolerance from drawdown reaction and horizon', async () => {
      const { emitted } = render(RiskCalibrationStep, {
        props: { initialHorizonYears: 15, initialReaction: 'hold' }
      });

      expect(screen.getByTestId('derived-tier-display').textContent).toContain('aggressive');

      // Click Sell reaction -> switches to conservative
      const sellOpt = screen.getByTestId('reaction-opt-sell');
      await fireEvent.click(sellOpt);
      expect(screen.getByTestId('derived-tier-display').textContent).toContain('conservative');

      const confirmBtn = screen.getByTestId('confirm-risk-calibration-btn');
      await fireEvent.click(confirmBtn);

      expect(emitted().next).toBeTruthy();
      const payload = (emitted().next as any)[0][0];
      expect(payload.riskTolerance).toBe('conservative');
      expect(payload.drawdownReaction).toBe('sell');
      expect(payload.defaultBands.length).toBe(3);
    });
  });

  describe('Turn 4: TargetAllocationStep.vue', () => {
    it('renders target allocation and min-max tolerance bands, validating 100% total', async () => {
      const { emitted } = render(TargetAllocationStep, {
        props: {
          initialBands: [
            { asset_class: 'Equities (US & Global)', target_percent: 60, min_percent: 50, max_percent: 70 },
            { asset_class: 'Fixed Income (Bonds)', target_percent: 30, min_percent: 20, max_percent: 40 },
            { asset_class: 'Cash & Equivalents', target_percent: 10, min_percent: 5, max_percent: 15 }
          ]
        }
      });

      expect(screen.getByTestId('total-percent-display').textContent).toBe('100%');
      expect(screen.getByTestId('projected-return').textContent).toContain('6.1%');
      expect(screen.getAllByTestId('band-row').length).toBe(3);

      // Adjust equity target to 70% (total becomes 110%)
      const inputEq = screen.getByTestId('input-target-0');
      await fireEvent.update(inputEq, '70');

      expect(screen.getByTestId('allocation-warning')).toBeDefined();
      const confirmBtn = screen.getByTestId('confirm-allocation-btn') as HTMLButtonElement;
      expect(confirmBtn.disabled).toBe(true);

      // Fix total to 100%: adjust fixed income to 20%
      const inputFi = screen.getByTestId('input-target-1');
      await fireEvent.update(inputFi, '20');

      expect(screen.queryByTestId('allocation-warning')).toBeNull();
      expect(confirmBtn.disabled).toBe(false);

      await fireEvent.click(confirmBtn);
      expect(emitted().confirm).toBeTruthy();
      const confirmedBands = (emitted().confirm as any)[0][0];
      expect(confirmedBands[0].target_percent).toBe(70);
      expect(confirmedBands[1].target_percent).toBe(20);
    });
  });

  describe('Turn 5: ConstraintsStep.vue', () => {
    it('collects reserve months, concentration limits, exclusions, and approval thresholds', async () => {
      const { emitted } = render(ConstraintsStep);

      await fireEvent.update(screen.getByTestId('input-reserve-months'), '9');
      await fireEvent.update(screen.getByTestId('input-concentration-limit'), '10');
      await fireEvent.update(screen.getByTestId('input-excluded-tickers'), 'TSLA, XOM');
      await fireEvent.update(screen.getByTestId('input-excluded-sectors'), 'tobacco, defense');
      await fireEvent.update(screen.getByTestId('input-approval-usd'), '2500');
      await fireEvent.update(screen.getByTestId('input-approval-pct'), '10');

      const confirmBtn = screen.getByTestId('confirm-constraints-btn');
      await fireEvent.click(confirmBtn);

      expect(emitted().next).toBeTruthy();
      const payload = (emitted().next as any)[0][0];
      expect(payload.reserveMonths).toBe(9);
      expect(payload.constraints.concentration_limit_percent).toBe(10);
      expect(payload.constraints.excluded_tickers).toEqual(['TSLA', 'XOM']);
      expect(payload.constraints.excluded_sectors).toEqual(['tobacco', 'defense']);
      expect(payload.thresholds.approval_required_above_usd).toBe(2500);
      expect(payload.thresholds.approval_required_above_percent).toBe(10);
    });
  });

  describe('Turn 6: SubmissionStep.vue', () => {
    it('renders synthesized IPS summary and invokes apiService.triggerPlan on submit', async () => {
      const planSpy = vi.spyOn(apiService, 'triggerPlan').mockResolvedValue(new Response('{}', { status: 200 }));

      render(SubmissionStep, {
        props: {
          state: {
            step: 7,
            user_id: 'test_user',
            goals: [{ name: 'Growth', target_amount_usd: 1000000, target_date: '2035-01-01' }],
            time_horizon_years: 15,
            known_upcoming_expenses_usd: 0,
            liabilities: [{ liability_id: '1', type: 'credit_card', description: 'Card', balance_usd: 1000, interest_rate_percent: 20, minimum_payment_usd: 50 }],
            drawdown_reaction: 'buy_more',
            risk_tolerance: 'aggressive',
            target_bands: [
              { asset_class: 'Equities (US & Global)', target_percent: 85, min_percent: 75, max_percent: 95 },
              { asset_class: 'Fixed Income (Bonds)', target_percent: 10, min_percent: 0, max_percent: 20 },
              { asset_class: 'Cash & Equivalents', target_percent: 5, min_percent: 0, max_percent: 10 }
            ],
            reserve_months: 6,
            constraints: { concentration_limit_percent: 15, excluded_tickers: [], excluded_sectors: [] },
            approval_thresholds: { approval_required_above_usd: 1000, approval_required_above_percent: 5 }
          }
        }
      });

      expect(screen.getByTestId('summary-risk-tier').textContent).toContain('aggressive');
      expect(screen.getByTestId('summary-horizon').textContent).toContain('15 Years');
      expect(screen.getAllByTestId('summary-band-row').length).toBe(3);

      const submitBtn = screen.getByTestId('submit-ips-btn');
      await fireEvent.click(submitBtn);

      expect(planSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          user_id: 'test_user'
        })
      );

      // Dashboard CTA is displayed after submission
      const dashboardBtn = screen.getByTestId('go-to-dashboard-btn');
      await fireEvent.click(dashboardBtn);
      expect(mockPush).toHaveBeenCalledWith('/');
    });
  });

  describe('OnboardingView.vue (Full 7-Step Turn-by-Turn Wizard)', () => {
    it('walks through all turns, computes deterministic risk, overrides bands, and submits plan', async () => {
      vi.spyOn(apiService, 'triggerPlan').mockResolvedValue(new Response('{}', { status: 200 }));

      render(OnboardingView);

      // Step 1: Welcome
      expect(screen.getByTestId('welcome-step')).toBeDefined();
      expect(screen.getByTestId('step-title').textContent).toContain('Welcome to Portfolio Copilot');
      await fireEvent.click(screen.getByTestId('start-setup-btn'));

      // Step 2: Goals & Timeline
      expect(screen.getByTestId('goals-step')).toBeDefined();
      expect(screen.getByTestId('step-title').textContent).toContain('Turn 1: Goals & Timeline');
      await fireEvent.click(screen.getByTestId('confirm-goals-btn'));

      // Step 3: Liabilities & Debt
      expect(screen.getByTestId('liabilities-step')).toBeDefined();
      expect(screen.getByTestId('step-title').textContent).toContain('Turn 2: Liabilities & Debt');
      await fireEvent.click(screen.getByTestId('confirm-liabilities-btn'));

      // Step 4: Risk Calibration
      expect(screen.getByTestId('risk-calibration-step')).toBeDefined();
      expect(screen.getByTestId('step-title').textContent).toContain('Turn 3: Risk Calibration');
      await fireEvent.click(screen.getByTestId('confirm-risk-calibration-btn'));

      // Step 5: Target Allocation & Bands
      expect(screen.getByTestId('target-allocation-step')).toBeDefined();
      expect(screen.getByTestId('step-title').textContent).toContain('Turn 4: Target Allocation Bands');
      await fireEvent.click(screen.getByTestId('confirm-allocation-btn'));

      // Step 6: Policy Constraints & Guardrails
      expect(screen.getByTestId('constraints-step')).toBeDefined();
      expect(screen.getByTestId('step-title').textContent).toContain('Turn 5: Policy Guardrails');
      await fireEvent.click(screen.getByTestId('confirm-constraints-btn'));

      // Step 7: Final Review & Submission
      expect(screen.getByTestId('submission-step')).toBeDefined();
      expect(screen.getByTestId('step-title').textContent).toContain('Turn 6: Review & Submission');

      await fireEvent.click(screen.getByTestId('submit-ips-btn'));
      await fireEvent.click(screen.getByTestId('go-to-dashboard-btn'));

      expect(mockPush).toHaveBeenCalledWith('/');
    });

    it('supports backward navigation via header back button', async () => {
      render(OnboardingView);

      await fireEvent.click(screen.getByTestId('start-setup-btn'));
      expect(screen.getByTestId('goals-step')).toBeDefined();

      // Click back -> returns to Welcome
      await fireEvent.click(screen.getByTestId('onboarding-back-btn'));
      expect(screen.getByTestId('welcome-step')).toBeDefined();

      // Click back on Step 1 -> navigates to /
      await fireEvent.click(screen.getByTestId('onboarding-back-btn'));
      expect(mockPush).toHaveBeenCalledWith('/');
    });
  });
});
