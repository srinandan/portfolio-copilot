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
