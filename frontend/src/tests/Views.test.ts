import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/vue';
import DashboardView from '../views/DashboardView.vue';
import PortfolioView from '../views/PortfolioView.vue';
import DocumentsView from '../views/DocumentsView.vue';
import { apiService } from '../services/api';

describe('Frontend Views', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiService, 'getDocuments').mockResolvedValue([
      {
        id: 'doc-1',
        filename: 'Fidelity_Stmt_Oct2023.pdf',
        size_bytes: 1258291,
        uploaded_at: '2023-10-24T09:41:00Z',
        status: 'SUCCESS',
        records_parsed: 42
      }
    ]);
    vi.spyOn(apiService, 'getHoldings').mockResolvedValue({
      total_value_usd: 1248500.0,
      cash_usd: 62400.0,
      as_of: '2023-10-24',
      positions: [
        {
          ticker: 'AAPL',
          name: 'Apple Inc.',
          asset_class: 'Equities (US)',
          quantity: 120,
          current_price_usd: 170.41,
          current_value_usd: 20449.2,
          change_percent: 1.2
        }
      ]
    });
    vi.spyOn(apiService, 'getDriftReport').mockResolvedValue({
      as_of: '2023-10-24',
      has_active_ips: true,
      rebalance_recommended: true,
      unclassified_value_usd: 0.0,
      bands: []
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('DashboardView renders prompt trigger, empty state, and financial canvas', async () => {
    render(DashboardView);
    expect(screen.getByTestId('btn-trigger-plan')).toBeDefined();
    expect(screen.getByText('Total Net Worth')).toBeDefined();
    expect(screen.getByText('Asset Allocation')).toBeDefined();

    // Before any turn runs, the dashboard shows a real empty state — no fake
    // demo message. The approval card only appears when a real HITL event
    // arrives.
    expect(screen.getByTestId('dashboard-empty-state')).toBeDefined();
    expect(screen.queryByTestId('approval-card')).toBeNull();
    expect(screen.getAllByTestId('example-prompt').length).toBeGreaterThan(0);
  });

  it('DashboardView triggers live plan, streams SSE events, and renders new HITL approval card', async () => {
    const streamPlanSpy = vi.spyOn(apiService, 'streamPlan').mockImplementation(async (_req, onEvent) => {
      onEvent({
        id: 'int_live_123',
        invocation_id: 'inv_live_456',
        session_id: 'sess_live_789',
        kind: 'hitl_approval_request',
        action: {
          action_id: 'act_rebal_999',
          session_id: 'sess_live_789',
          type: 'TRADE',
          ticker: 'MSFT',
          side: 'BUY',
          quantity: 20,
          rationale: 'Add MSFT per tech allocation band',
          status: 'DRAFTED'
        },
        reviewer_verdict: {
          verdict_id: 'verd_999',
          action_id: 'act_rebal_999',
          overall_pass: true,
          requires_human_approval: true,
          rule_results: [
            { rule_id: 'rule_target', description: 'Moves closer to IPS target', passed: true }
          ]
        }
      });
    });

    render(DashboardView);
    const input = screen.getByPlaceholderText(/Ask Copilot/i);
    await fireEvent.update(input, 'Rebalance my portfolio now');

    const triggerBtn = screen.getByTestId('btn-trigger-plan');
    await fireEvent.click(triggerBtn);

    expect(streamPlanSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        user_id: 'demo_user',
        message: 'Rebalance my portfolio now'
      }),
      expect.any(Function),
      expect.any(Function)
    );

    await waitFor(() => {
      expect(screen.getByText('Action ID: act_rebal_999')).toBeDefined();
      expect(screen.getByText('MSFT')).toBeDefined();
    });
  });

  it('DashboardView renders the live progress stepper while an analysis is streaming, then clears it', async () => {
    // Regression: progress events arrive asynchronously over the SSE stream,
    // in ticks AFTER the initial render has settled. Mutating the raw agent
    // message object at that point does not trigger a Vue re-render, so the
    // stepper must be driven through the reactive array element. Delivering the
    // events in later ticks (below) is what exposes the bug; the pending promise
    // keeps the stream open so the stepper is asserted DURING streaming.
    let resolveStream: () => void = () => {};
    const tick = () => new Promise<void>((r) => setTimeout(r, 0));
    vi.spyOn(apiService, 'streamPlan').mockImplementation(async (_req, onEvent) => {
      await tick();
      onEvent({ kind: 'progress', stage: 'discovery', status: 'running', label: 'Discovering authorized skills' });
      await tick();
      onEvent({
        kind: 'progress',
        stage: 'discovery',
        status: 'done',
        label: 'Discovering authorized skills',
        detail: '5 authorized skill(s)'
      });
      onEvent({ kind: 'progress', stage: 'spending-analysis', status: 'running', label: 'Analyzing spending' });
      await new Promise<void>((r) => {
        resolveStream = r;
      });
    });

    render(DashboardView);
    await fireEvent.click(screen.getAllByTestId('example-prompt')[0]);

    // Wait until all asynchronously-delivered stages have rendered. That the
    // stepper appears at all from events fired in later ticks is the crux: the
    // raw-object binding never re-renders here.
    await waitFor(() => {
      expect(screen.getByTestId('analysis-progress')).toBeDefined();
      // discovery (upserted running -> done in place) + spending-analysis
      expect(screen.getAllByTestId('progress-stage').length).toBe(2);
    });
    const rows = screen.getAllByTestId('progress-stage');
    const byStage = (s: string) => rows.find((r) => r.getAttribute('data-stage') === s);
    expect(byStage('discovery')?.getAttribute('data-status')).toBe('done');
    expect(byStage('spending-analysis')?.getAttribute('data-status')).toBe('running');
    expect(screen.getByText('5 authorized skill(s)')).toBeDefined();

    // Completing the run clears the stepper so the final output can replace it.
    resolveStream();
    await waitFor(() => {
      expect(screen.queryByTestId('analysis-progress')).toBeNull();
    });
  });

  it('DashboardView keeps suggestion prompts after a turn and renders responses as prose (not raw JSON)', async () => {
    vi.spyOn(apiService, 'streamPlan').mockImplementation(async (_req, onEvent) => {
      onEvent({
        author: 'portfolio_copilot_planner',
        output: ["spending-analysis_result: {'narrative_summary': 'You saved 40% of income this quarter.'}"]
      });
    });

    render(DashboardView);
    const prompts = screen.getAllByTestId('example-prompt');
    await fireEvent.click(prompts[0]);

    await waitFor(() => {
      // Empty state is gone once a conversation starts...
      expect(screen.queryByTestId('dashboard-empty-state')).toBeNull();
      // ...but the suggestion chips persist so users can keep asking.
      expect(screen.getAllByTestId('example-prompt').length).toBeGreaterThan(0);
      // The agent reply is rendered as prose, not a raw JSON blob.
      expect(screen.getByText(/You saved 40% of income this quarter\./)).toBeDefined();
      expect(screen.queryByText(/narrative_summary/)).toBeNull();
    });
  });

  it('DashboardView clears previous agent responses when the user starts a new interaction', async () => {
    let callCount = 0;
    vi.spyOn(apiService, 'streamPlan').mockImplementation(async (_req, onEvent) => {
      callCount += 1;
      onEvent({
        author: 'portfolio_copilot_planner',
        output: [`Turn ${callCount} response`]
      });
    });

    render(DashboardView);
    const prompts = screen.getAllByTestId('example-prompt');

    // Turn 1
    await fireEvent.click(prompts[0]);
    await waitFor(() => {
      expect(screen.getByText(/Turn 1 response/)).toBeDefined();
    });

    // Turn 2: should clear Turn 1 message and show Turn 2 message
    await fireEvent.click(prompts[1]);
    await waitFor(() => {
      expect(screen.getByText(/Turn 2 response/)).toBeDefined();
      expect(screen.queryByText(/Turn 1 response/)).toBeNull();
    });
  });

  it('DashboardView renders the ApprovalCard from an ADK adk_request_input function-call event', async () => {
    // The real HITL request arrives as a function-call whose args.message holds
    // the payload — not as event.output/kind. The card must still render.
    vi.spyOn(apiService, 'streamPlan').mockImplementation(async (_req, onEvent) => {
      onEvent({
        id: 'evt_1',
        invocation_id: 'inv_1',
        content: {
          parts: [
            {
              function_call: {
                id: 'int_fc_1',
                name: 'adk_request_input',
                args: {
                  interruptId: 'int_fc_1',
                  message: JSON.stringify({
                    kind: 'hitl_approval_request',
                    action: {
                      action_id: 'act_fc_1',
                      ticker: 'VTI',
                      side: 'sell',
                      quantity: 25,
                      status: 'drafted',
                      rationale: '{"rationale":"Trim VTI back toward its target band.","supporting_research_refs":[]}'
                    },
                    reviewer_verdict: {
                      verdict_id: 'v_fc_1',
                      overall_pass: true,
                      requires_human_approval: true,
                      rule_results: []
                    }
                  })
                }
              }
            }
          ]
        }
      });
    });

    render(DashboardView);
    await fireEvent.click(screen.getAllByTestId('example-prompt')[0]);

    await waitFor(() => {
      expect(screen.getByTestId('approval-card')).toBeDefined();
      expect(screen.getByText('Action ID: act_fc_1')).toBeDefined();
      expect(screen.getByText('VTI')).toBeDefined();
      // The JSON-encoded rationale is unwrapped to its inner text, not shown raw.
      expect(screen.getByText(/Trim VTI back toward its target band\./)).toBeDefined();
      expect(screen.queryByText(/supporting_research_refs/)).toBeNull();
    });
  });

  // Helper: mock streamPlan to synchronously deliver a HITL approval request
  // and then trigger a plan run so the ApprovalCard is on screen.
  const seedApprovalCard = async (rationale = 'Rebalance rationale') => {
    vi.spyOn(apiService, 'streamPlan').mockImplementation(async (_req, onEvent) => {
      onEvent({
        id: 'int_seed_1',
        invocation_id: 'inv_seed_1',
        session_id: 'sess_seed_1',
        kind: 'hitl_approval_request',
        action: {
          action_id: 'act_seed_1',
          session_id: 'sess_seed_1',
          type: 'trade',
          ticker: 'MSFT',
          side: 'buy',
          quantity: 20,
          rationale,
          status: 'drafted'
        },
        reviewer_verdict: {
          verdict_id: 'verd_seed_1',
          action_id: 'act_seed_1',
          overall_pass: true,
          requires_human_approval: true,
          rule_results: []
        }
      });
    });
    render(DashboardView);
    const prompts = screen.getAllByTestId('example-prompt');
    await fireEvent.click(prompts[0]);
    await waitFor(() => {
      expect(screen.getByTestId('approval-card')).toBeDefined();
    });
  };

  it('DashboardView allows approving actions and resumes plan via apiService.streamPlanResume', async () => {
    const resumeSpy = vi.spyOn(apiService, 'streamPlanResume').mockResolvedValue();
    await seedApprovalCard();

    const approveBtn = screen.getByTestId('btn-approve');
    await fireEvent.click(approveBtn);

    expect(resumeSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        user_id: 'demo_user',
        payload: { decision: 'approve', user_id: 'demo_user' }
      }),
      expect.any(Function),
      expect.any(Function)
    );

    expect(screen.getByText(/APPROVED — Execution Triggered/i)).toBeDefined();
  });

  it('DashboardView allows rejecting actions and resumes plan via apiService.streamPlanResume', async () => {
    const resumeSpy = vi.spyOn(apiService, 'streamPlanResume').mockResolvedValue();
    await seedApprovalCard();

    const rejectBtn = screen.getByTestId('btn-reject');
    await fireEvent.click(rejectBtn);

    expect(resumeSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        user_id: 'demo_user',
        payload: {
          decision: 'reject',
          reason: 'User rejected proposed trade',
          user_id: 'demo_user'
        }
      }),
      expect.any(Function),
      expect.any(Function)
    );

    expect(screen.getByText(/REJECTED — Trade Aborted/i)).toBeDefined();
  });

  it('DashboardView allows editing actions and saves changes via apiService.streamPlanResume', async () => {
    const resumeSpy = vi.spyOn(apiService, 'streamPlanResume').mockResolvedValue();
    await seedApprovalCard('Original rationale');

    const editBtn = screen.getByTestId('btn-edit');
    await fireEvent.click(editBtn);

    const qtyInput = screen.getByTestId('edit-quantity-input');
    await fireEvent.update(qtyInput, '30');

    const saveBtn = screen.getByText('Save Changes');
    await fireEvent.click(saveBtn);

    expect(resumeSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        user_id: 'demo_user',
        payload: {
          decision: 'edit',
          changes: {
            quantity: 30,
            rationale: 'Original rationale'
          },
          user_id: 'demo_user'
        }
      }),
      expect.any(Function),
      expect.any(Function)
    );
  });

  it('PortfolioView renders total value chart and top holdings list', async () => {
    render(PortfolioView);
    expect(screen.getByText('Total Value')).toBeDefined();
    expect(screen.getByText('Portfolio Drift Report')).toBeDefined();
    expect(screen.getByText('Top Holdings')).toBeDefined();
    expect(screen.getAllByTestId('allocation-row').length).toBeGreaterThan(0);

    await waitFor(() => {
      expect(screen.getByText('$1,248,500.00')).toBeDefined();
    });
  });

  it('DocumentsView renders ingestion dropzone and documents history table', async () => {
    render(DocumentsView);
    expect(screen.getByTestId('documents-view')).toBeDefined();
    expect(screen.getByText('Documents & File Ingestion')).toBeDefined();
    expect(screen.getByTestId('upload-dropzone')).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText('Fidelity_Stmt_Oct2023.pdf')).toBeDefined();
      expect(screen.getByText('42')).toBeDefined();
    });
  });

  it('OnboardingView renders initial step and step title', async () => {
    const OnboardingView = (await import('../views/OnboardingView.vue')).default;
    const { router } = await import('../router');
    render(OnboardingView, {
      global: {
        plugins: [router]
      }
    });

    expect(screen.getAllByText('Welcome to Portfolio Copilot').length).toBeGreaterThan(0);
    expect(screen.getByTestId('step-title').textContent).toContain('Welcome to Portfolio Copilot');
  });

  it('ProfileView renders profile & policy hub with tabs and handles full save', async () => {
    const ProfileView = (await import('../views/ProfileView.vue')).default;
    const { router } = await import('../router');
    const mockProfile = {
      user_id: 'demo_user',
      full_name: 'Alex Mercer',
      email: 'alex.mercer@example.com',
      date_of_birth: '1980-06-15',
      age: 46,
      marital_status: 'married',
      dependents_count: 2,
      family_members: [{ name: 'Sarah', relationship: 'spouse', age: 44 }],
      employment_status: 'employed',
      occupation: 'Engineer',
      annual_income_usd: 220000,
      target_retirement_age: 61,
      monthly_housing_payment_usd: 4200,
      risk_tolerance_notes: 'Moderate risk notes',
      financial_goals_notes: 'Retirement by 2041',
      updated_at: '2026-08-01T00:00:00Z'
    };

    const mockOnboarding = {
      has_active_ips: true,
      user_id: 'demo_user',
      version: 2,
      time_horizon_years: 15,
      risk_tolerance: 'aggressive' as const,
      goals: [
        { name: 'Retirement Compounding', target_amount_usd: 1500000, target_date: '2039-12-31' }
      ],
      target_bands: [
        { asset_class: 'Equities (US & Global)', target_percent: 85, min_percent: 75, max_percent: 95 },
        { asset_class: 'Fixed Income (Bonds)', target_percent: 10, min_percent: 0, max_percent: 20 },
        { asset_class: 'Cash & Equivalents', target_percent: 5, min_percent: 0, max_percent: 10 }
      ],
      liabilities: [
        {
          liability_id: 'liab_001',
          type: 'credit_card' as const,
          description: 'Premium Rewards Card',
          balance_usd: 4850,
          interest_rate_percent: 24.99,
          minimum_payment_usd: 150
        }
      ],
      constraints: {
        concentration_limit_percent: 15,
        excluded_tickers: ['TSLA'],
        excluded_sectors: ['tobacco'],
        account_type: 'taxable' as const,
        tax_loss_harvesting_enabled: true
      },
      approval_required_above_usd: 1000,
      approval_required_above_percent: 5
    };

    vi.spyOn(apiService, 'getUserProfile').mockResolvedValue(mockProfile);
    vi.spyOn(apiService, 'getOnboarding').mockResolvedValue(mockOnboarding);

    const updateProfileSpy = vi.spyOn(apiService, 'updateUserProfile').mockResolvedValue({
      status: 'ok',
      profile: { ...mockProfile, full_name: 'Alex Mercer Updated' }
    });

    const applyOnboardingSpy = vi.spyOn(apiService, 'applyOnboarding').mockResolvedValue({
      status: 'applied',
      ips_id: 'ips_test_1',
      version: 3,
      liabilities_count: 1
    });

    render(ProfileView, {
      global: {
        plugins: [router]
      }
    });

    await waitFor(() => {
      expect((screen.getByTestId('input-full-name') as HTMLInputElement).value).toBe('Alex Mercer');
      expect((screen.getByTestId('input-email') as HTMLInputElement).value).toBe('alex.mercer@example.com');
      expect(screen.getByTestId('badge-ips-status').textContent).toContain('Active IPS (v2)');
    });

    // Test adding and removing family members in Personal tab
    const addMemberBtn = screen.getByTestId('btn-add-family-member');
    await fireEvent.click(addMemberBtn);
    expect(screen.getAllByTestId('family-member-row').length).toBe(2);

    const removeMemberBtns = screen.getAllByTestId('btn-remove-family-member');
    await fireEvent.click(removeMemberBtns[0]);
    expect(screen.getAllByTestId('family-member-row').length).toBe(1);

    // Switch to Goals tab and verify controls
    const goalsTabBtn = screen.getByTestId('tab-goals');
    await fireEvent.click(goalsTabBtn);
    expect(screen.getByTestId('section-goals')).toBeDefined();

    const addGoalBtn = screen.getByTestId('btn-add-goal');
    await fireEvent.click(addGoalBtn);
    expect(screen.getAllByTestId('goal-item-row').length).toBe(2);

    // Switch to Risk tab and verify reaction / allocation controls
    const riskTabBtn = screen.getByTestId('tab-risk');
    await fireEvent.click(riskTabBtn);
    expect(screen.getByTestId('section-risk')).toBeDefined();

    const holdOpt = screen.getByTestId('reaction-opt-hold');
    await fireEvent.click(holdOpt);
    expect(screen.getByTestId('total-percent-display').textContent?.trim()).toBe('100%');

    // Switch to Liabilities tab
    const liabilitiesTabBtn = screen.getByTestId('tab-liabilities');
    await fireEvent.click(liabilitiesTabBtn);
    expect(screen.getByTestId('section-liabilities')).toBeDefined();
    expect(screen.getByTestId('total-liabilities-display').textContent).toContain('$4,850');

    // Switch to Policy Guardrails tab
    const policyTabBtn = screen.getByTestId('tab-policy');
    await fireEvent.click(policyTabBtn);
    expect(screen.getByTestId('section-policy')).toBeDefined();

    // Trigger save
    const saveBtn = screen.getByTestId('btn-save-profile');
    await fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(updateProfileSpy).toHaveBeenCalled();
      expect(applyOnboardingSpy).toHaveBeenCalled();
      expect(screen.getByTestId('profile-save-success')).toBeDefined();
    });
  });

  it('ProfileView handles Income & Tax (W-2) tab with Document AI upload and 1-click sync', async () => {
    const ProfileView = (await import('../views/ProfileView.vue')).default;
    const { router } = await import('../router');
    const mockProfile = {
      user_id: 'demo_user',
      full_name: 'Alex Mercer',
      email: 'alex.mercer@example.com',
      annual_income_usd: 180000,
      updated_at: '2026-08-01T00:00:00Z'
    };

    const mockW2 = {
      id: 'w2-test-999',
      user_id: 'demo_user',
      tax_year: 2024,
      status: 'SUCCESS' as const,
      employer: {
        name: 'Alphabet Inc.',
        ein: '94-3289634'
      },
      employee: {
        name: 'Alex Mercer',
        ssn_masked: '***-**-4589'
      },
      wages_and_compensation: {
        box1_wages_tips_other_comp_usd: 245000,
        box2_federal_income_tax_withheld_usd: 42000,
        box3_social_security_wages_usd: 168600,
        box5_medicare_wages_and_tips_usd: 245000
      },
      box12_items: [
        { code: 'D', description: '401(k) elective deferral', amount_usd: 23000 }
      ],
      uploaded_at: '2026-08-22T00:00:00Z'
    };

    vi.spyOn(apiService, 'getUserProfile').mockResolvedValue(mockProfile);
    vi.spyOn(apiService, 'getOnboarding').mockResolvedValue({
      has_active_ips: false,
      user_id: 'demo_user'
    });
    vi.spyOn(apiService, 'getW2Documents').mockResolvedValue([mockW2]);
    const uploadW2Spy = vi.spyOn(apiService, 'uploadW2').mockResolvedValue(mockW2);
    const applyW2Spy = vi.spyOn(apiService, 'applyW2ToProfile').mockResolvedValue({
      status: 'applied',
      profile: {
        ...mockProfile,
        annual_income_usd: 245000,
        occupation: 'Engineer at Alphabet Inc.'
      }
    });

    render(ProfileView, {
      global: {
        plugins: [router]
      }
    });

    // Switch to Income & Tax tab
    const incomeTabBtn = screen.getByTestId('tab-income');
    await fireEvent.click(incomeTabBtn);
    expect(screen.getByTestId('section-income')).toBeDefined();

    // Verify W-2 card is rendered
    await waitFor(() => {
      expect(screen.getByText('Tax Year 2024')).toBeDefined();
      expect(screen.getByText('Alphabet Inc.')).toBeDefined();
      expect(screen.getByTestId('w2-box1-wages').textContent).toContain('$245,000');
    });

    // Test 1-click sync to profile
    const applyBtn = screen.getByTestId('btn-apply-w2');
    await fireEvent.click(applyBtn);

    await waitFor(() => {
      expect(applyW2Spy).toHaveBeenCalledWith('w2-test-999', 'demo_user');
      expect(screen.getByTestId('w2-upload-success').textContent).toContain('Successfully synchronized Box 1 wages');
    });

    // Test W-2 File Upload
    const file = new File(['%PDF-1.4 mock content'], 'w2_2024.pdf', { type: 'application/pdf' });
    const fileInput = screen.getByTestId('input-w2-file');
    await fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(uploadW2Spy).toHaveBeenCalled();
    });
  });
});


