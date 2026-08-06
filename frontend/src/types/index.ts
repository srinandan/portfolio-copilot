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

export interface ProposedAction {
  action_id: string;
  session_id: string;
  type: 'TRADE' | 'TRANSFER' | 'REBALANCE';
  ticker?: string;
  side?: 'BUY' | 'SELL';
  quantity?: number;
  order_type?: string;
  estimated_price_usd?: number;
  estimated_value_usd?: number;
  rationale: string;
  status: 'DRAFTED' | 'APPROVED' | 'REJECTED' | 'EXECUTED' | 'FAILED';
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'agent' | 'system';
  text: string;
  timestamp: string;
  action?: ProposedAction;
  verdict?: ReviewerVerdict;
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

export interface TargetAllocationInput {
  equity: number;
  fixed_income: number;
  cash: number;
}

export interface OnboardingState {
  step: number;
  objective: string;
  time_horizon_years: number;
  drawdown_reaction: 'sell' | 'hold' | 'buy_more';
  risk_tolerance: RiskToleranceTier;
  target_allocation: TargetAllocationInput;
  uploaded_file?: {
    name: string;
    size_bytes: number;
    records_parsed: number;
  };
}

