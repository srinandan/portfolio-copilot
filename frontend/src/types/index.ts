export interface HealthStatus {
  status: string;
}

export interface Position {
  ticker: string;
  name?: string;
  asset_class: string;
  quantity: number;
  market_value_usd?: number;
  current_price_usd?: number;
  current_value_usd?: number;
  change_percent?: number;
  account_type?: string;
}

export interface HoldingsSnapshot {
  total_value_usd: number;
  cash_usd: number;
  positions: Position[];
  as_of: string;
}

export interface DocumentItem {
  id: string;
  user_id?: string;
  filename: string;
  document_type?: 'transactions' | 'holdings' | 'liabilities' | 'ips' | string;
  account_type?: string;
  target_table?: string;
  size_bytes: number;
  uploaded_at: string;
  status: 'SUCCESS' | 'PROCESSING' | 'FAILED';
  records_parsed?: number;
  error_message?: string;
}

export interface RuleResult {
  rule_id: string;
  description: string;
  passed: boolean;
}

export interface ReviewerVerdict {
  verdict_id: string;
  action_id: string;
  rule_results: RuleResult[];
  overall_pass: boolean;
  requires_human_approval: boolean;
}

export type ActionType = 'trade' | 'transfer' | 'rebalance' | 'TRADE' | 'TRANSFER' | 'REBALANCE';
export type ActionSide = 'buy' | 'sell' | 'BUY' | 'SELL';
export type ActionStatus =
  | 'drafted'
  | 'reviewed_pass'
  | 'reviewed_fail'
  | 'pending_approval'
  | 'approved'
  | 'rejected'
  | 'executed'
  | 'failed'
  | 'DRAFTED'
  | 'REVIEWED_PASS'
  | 'REVIEWED_FAIL'
  | 'PENDING_APPROVAL'
  | 'APPROVED'
  | 'REJECTED'
  | 'EXECUTED'
  | 'FAILED'
  | 'PENDING';

export interface ProposedAction {
  action_id: string;
  session_id: string;
  type: ActionType;
  ticker?: string;
  side?: ActionSide;
  quantity?: number;
  order_type?: string;
  estimated_price_usd?: number;
  estimated_value_usd?: number;
  rationale: string;
  status: ActionStatus;
}

export type ProgressStatus = 'pending' | 'running' | 'done' | 'skipped' | 'failed';

/**
 * A single pipeline stage surfaced live while an analysis runs. Emitted by the
 * orchestrator as `{ kind: 'progress', ... }` SSE events and rendered as one row
 * of the AnalysisProgress stepper. Advisory UI signal only — never authoritative.
 */
export interface ProgressStage {
  stage: string;
  label: string;
  status: ProgressStatus;
  detail?: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'agent' | 'system';
  text: string;
  timestamp: string;
  action?: ProposedAction;
  verdict?: ReviewerVerdict;
  session_id?: string;
  invocation_id?: string;
  interrupt_id?: string;
  // Live analysis progress. `progress` accumulates stage rows; `progressActive`
  // is true while the stepper should render (cleared when the run finishes so
  // the final output replaces it).
  progress?: ProgressStage[];
  progressActive?: boolean;
  startedAt?: number;
}

export interface CategorySpending {
  category:
    | 'housing' | 'utilities' | 'groceries' | 'dining' | 'transportation'
    | 'entertainment' | 'subscriptions' | 'healthcare' | 'travel' | 'shopping'
    | 'income' | 'transfers' | 'fees' | 'other';
  amount_usd: number;
  percent_of_total: number;
  monthly_average_usd?: number;
}

export interface SpendingAnomaly {
  category: string;
  amount_usd: number;
  trailing_average_usd: number;
  description: string;
  date: string;
}

export interface SpendingReport {
  user_id: string;
  total_income_usd: number;
  total_outflow_usd: number;
  savings_rate: number;
  reserve_months: number;
  category_breakdown: CategorySpending[];
  anomalies: SpendingAnomaly[];
  narrative_summary: string;
}

export interface DriftBandItem {
  asset_class: string;
  current_percent: number;
  target_percent: number;
  min_percent: number;
  max_percent: number;
  in_band: boolean;
  drift_amount_percent: number;
}

export interface DriftReport {
  as_of: string;
  bands: DriftBandItem[];
  unclassified_value_usd: number;
  rebalance_recommended: boolean;
  has_active_ips: boolean;
}

export type RiskToleranceTier = 'conservative' | 'moderate' | 'aggressive';
export type DrawdownReaction = 'sell' | 'hold' | 'buy_more';

export interface Goal {
  name: string;
  target_amount_usd: number;
  target_date: string;
}

export interface LiabilityItem {
  liability_id: string;
  type: 'credit_card' | 'mortgage' | 'auto_loan' | 'student_loan' | 'heloc' | 'other';
  description: string;
  balance_usd: number;
  interest_rate_percent: number;
  minimum_payment_usd: number;
}

export interface AllocationBand {
  asset_class: string;
  target_percent: number;
  min_percent: number;
  max_percent: number;
}

export interface IPSConstraints {
  concentration_limit_percent: number;
  excluded_tickers: string[];
  excluded_sectors: string[];
  account_type?: 'taxable' | 'retirement';
  tax_loss_harvesting_enabled?: boolean;
}

export interface ApprovalThresholds {
  approval_required_above_usd: number;
  approval_required_above_percent: number;
}

export interface OnboardingState {
  step: number;
  user_id: string;
  // Goals & Horizon
  goals: Goal[];
  time_horizon_years: number;
  known_upcoming_expenses_usd: number;
  // Liabilities
  liabilities: LiabilityItem[];
  // Risk Calibration
  drawdown_reaction: DrawdownReaction;
  risk_tolerance: RiskToleranceTier;
  // Target Allocation Bands
  target_bands: AllocationBand[];
  // Constraints & Thresholds
  reserve_months: number;
  constraints: IPSConstraints;
  approval_thresholds: ApprovalThresholds;
  // Execution / Submission
  submitting?: boolean;
  submission_error?: string;
  submitted?: boolean;
}

export interface FamilyMember {
  name: string;
  relationship: string;
  age: number;
}

export interface UserProfile {
  user_id: string;
  full_name?: string;
  email?: string;
  date_of_birth?: string;
  age?: number;
  marital_status?: 'single' | 'married' | 'partnered' | 'divorced' | 'widowed' | 'other' | string;
  dependents_count?: number;
  family_members?: FamilyMember[];
  employment_status?: 'employed' | 'self_employed' | 'retired' | 'student' | 'unemployed' | 'other' | string;
  occupation?: string;
  annual_income_usd?: number;
  target_retirement_age?: number;
  monthly_housing_payment_usd?: number;
  risk_tolerance_notes?: string;
  financial_goals_notes?: string;
  updated_at?: string;
}

export interface OnboardingProfile {
  has_active_ips: boolean;
  user_id: string;
  ips_id?: string;
  version?: number;
  goals?: Goal[];
  time_horizon_years?: number;
  known_upcoming_expenses_usd?: number;
  reserve_months?: number;
  risk_tolerance?: RiskToleranceTier;
  target_bands?: AllocationBand[];
  constraints?: IPSConstraints;
  approval_required_above_usd?: number;
  approval_required_above_percent?: number;
  liabilities?: LiabilityItem[];
}

export interface W2Employer {
  name?: string;
  ein?: string;
  address?: string;
}

export interface W2Employee {
  name?: string;
  ssn_masked?: string;
  address?: string;
}

export interface W2Wages {
  box1_wages_tips_other_comp_usd: number;
  box2_federal_income_tax_withheld_usd?: number;
  box3_social_security_wages_usd?: number;
  box4_social_security_tax_withheld_usd?: number;
  box5_medicare_wages_and_tips_usd?: number;
  box6_medicare_tax_withheld_usd?: number;
  box7_social_security_tips_usd?: number;
  box8_allocated_tips_usd?: number;
  box10_dependent_care_benefits_usd?: number;
  box11_nonqualified_plans_usd?: number;
}

export interface W2Box12Item {
  code: string;
  description?: string;
  amount_usd: number;
}

export interface W2Box13Checkboxes {
  statutory_employee?: boolean;
  retirement_plan?: boolean;
  third_party_sick_pay?: boolean;
}

export interface W2OtherItem {
  label: string;
  amount_usd: number;
}

export interface W2StateTax {
  state: string;
  employer_state_id?: string;
  state_wages_usd: number;
  state_income_tax_usd: number;
}

export interface W2LocalTax {
  locality_name: string;
  local_wages_usd: number;
  local_income_tax_usd: number;
}

export interface W2Document {
  id: string;
  user_id: string;
  tax_year: number;
  document_id?: string;
  filename?: string;
  size_bytes?: number;
  uploaded_at: string;
  parsed_at?: string;
  confidence_score?: number;
  status: 'SUCCESS' | 'FAILED' | 'PENDING_REVIEW';
  error_message?: string;
  employer?: W2Employer;
  employee?: W2Employee;
  wages_and_compensation: W2Wages;
  box12_items?: W2Box12Item[];
  box13_checkboxes?: W2Box13Checkboxes;
  box14_other?: W2OtherItem[];
  state_taxes?: W2StateTax[];
  local_taxes?: W2LocalTax[];
  raw_entities?: Record<string, string>;
}

// ---- Equity research + suitability (advisory analysis, issue #344) ----

export type ValuationVerdict = 'undervalued' | 'fairly_valued' | 'overvalued' | 'unknown';
export type ConfidenceLevel = 'high' | 'medium' | 'low';
export type RecommendationDirection = 'buy' | 'add' | 'hold' | 'trim' | 'avoid';

export interface DcfResult {
  intrinsic_value_per_share_usd?: number | null;
  current_price_usd?: number | null;
  upside_pct?: number | null;
  discount_rate: number;
  terminal_growth_rate: number;
  fcf_growth_rate: number;
  projection_years: number;
}

export interface QualityMetrics {
  net_margin_pct?: number | null;
  fcf_margin_pct?: number | null;
  revenue_cagr_pct?: number | null;
  return_on_equity_pct?: number | null;
  debt_to_equity?: number | null;
}

export interface EquityAssessment {
  ticker: string;
  company_name?: string | null;
  data_source: string;
  dcf?: DcfResult | null;
  quality?: QualityMetrics | null;
  valuation_verdict: ValuationVerdict;
  confidence: ConfidenceLevel;
  key_drivers: string[];
  key_risks: string[];
  disclaimers: string[];
  narrative_summary?: string;
}

export interface SuitabilityFactor {
  name: string;
  detail: string;
  favorable?: boolean | null;
}

export interface EquityRecommendation {
  ticker: string;
  direction: RecommendationDirection;
  conviction: ConfidenceLevel;
  rationale: string;
  valuation_verdict: ValuationVerdict;
  upside_pct?: number | null;
  assessment_confidence: ConfidenceLevel;
  already_held: boolean;
  current_weight_pct: number;
  concentration_limit_pct?: number | null;
  headroom_pct?: number | null;
  suitability_factors: SuitabilityFactor[];
  key_risks: string[];
  disclaimers: string[];
}

export interface EquityAnalysisResult {
  ticker: string;
  assessment: EquityAssessment;
  recommendation: EquityRecommendation;
}



