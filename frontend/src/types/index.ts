export interface HealthStatus {
  status: string;
}

export interface AuthCheckResult {
  project_id?: string;
  message?: string;
  error?: string;
}

export interface Position {
  ticker: string;
  name: string;
  asset_class: string;
  quantity: number;
  current_price_usd: number;
  current_value_usd: number;
  change_percent?: number;
}

export interface HoldingsSnapshot {
  total_value_usd: number;
  cash_usd: number;
  positions: Position[];
  as_of: string;
}

export interface DocumentItem {
  id: string;
  filename: string;
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
  account_type?: 'taxable' | 'ira' | 'roth_ira' | '401k';
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


