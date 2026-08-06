import type { RiskToleranceTier, DrawdownReaction, AllocationBand } from '../types';

/**
 * Deterministically derives risk_tolerance from time horizon in years and drawdown reaction.
 * Implements the deterministic mapping defined in skills/goals-onboarding/SKILL.md §Risk tolerance:
 *
 * | time_horizon_years | drawdown_reaction | → risk_tolerance |
 * | ≥ 15               | hold or buy_more  | aggressive       |
 * | ≥ 7                | hold or buy_more  | moderate         |
 * | any                | sell              | conservative     |
 * | < 7                | hold or buy_more  | moderate         |
 */
export function deriveRiskTolerance(
  timeHorizonYears: number,
  drawdownReaction: DrawdownReaction
): RiskToleranceTier {
  if (drawdownReaction === 'sell') {
    return 'conservative';
  }
  if (timeHorizonYears >= 15 && (drawdownReaction === 'hold' || drawdownReaction === 'buy_more')) {
    return 'aggressive';
  }
  if (timeHorizonYears >= 7 && (drawdownReaction === 'hold' || drawdownReaction === 'buy_more')) {
    return 'moderate';
  }
  return 'moderate';
}

/**
 * Returns the default target allocation bands per risk tolerance tier as specified in
 * skills/goals-onboarding/SKILL.md §Target allocation:
 *
 * - conservative: equity 30% (20–40), bonds 60% (50–70), cash 10% (5–15)
 * - moderate:     equity 60% (50–70), bonds 30% (20–40), cash 10% (5–15)
 * - aggressive:   equity 85% (75–95), bonds 10% (0–20),  cash 5% (0–10)
 */
export function getDefaultAllocationBands(tier: RiskToleranceTier): AllocationBand[] {
  switch (tier) {
    case 'conservative':
      return [
        { asset_class: 'Equities (US & Global)', target_percent: 30, min_percent: 20, max_percent: 40 },
        { asset_class: 'Fixed Income (Bonds)', target_percent: 60, min_percent: 50, max_percent: 70 },
        { asset_class: 'Cash & Equivalents', target_percent: 10, min_percent: 5, max_percent: 15 }
      ];
    case 'aggressive':
      return [
        { asset_class: 'Equities (US & Global)', target_percent: 85, min_percent: 75, max_percent: 95 },
        { asset_class: 'Fixed Income (Bonds)', target_percent: 10, min_percent: 0, max_percent: 20 },
        { asset_class: 'Cash & Equivalents', target_percent: 5, min_percent: 0, max_percent: 10 }
      ];
    case 'moderate':
    default:
      return [
        { asset_class: 'Equities (US & Global)', target_percent: 60, min_percent: 50, max_percent: 70 },
        { asset_class: 'Fixed Income (Bonds)', target_percent: 30, min_percent: 20, max_percent: 40 },
        { asset_class: 'Cash & Equivalents', target_percent: 10, min_percent: 5, max_percent: 15 }
      ];
  }
}
