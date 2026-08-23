import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/vue';
import { describe, it, expect, vi, afterEach } from 'vitest';
import EquityRecommendationCard from '../components/portfolio/EquityRecommendationCard.vue';
import EquityAnalyzer from '../components/portfolio/EquityAnalyzer.vue';
import { apiService } from '../services/api';
import type { EquityAnalysisResult } from '../types';

const fixture: EquityAnalysisResult = {
  ticker: 'AAPL',
  assessment: {
    ticker: 'AAPL',
    company_name: 'Apple Inc.',
    data_source: 'sec_edgar',
    dcf: {
      intrinsic_value_per_share_usd: 250,
      current_price_usd: 200,
      upside_pct: 25,
      discount_rate: 0.09,
      terminal_growth_rate: 0.025,
      fcf_growth_rate: 0.04,
      projection_years: 5
    },
    quality: null,
    valuation_verdict: 'undervalued',
    confidence: 'high',
    key_drivers: [],
    key_risks: [],
    disclaimers: []
  },
  recommendation: {
    ticker: 'AAPL',
    direction: 'buy',
    conviction: 'high',
    rationale: 'AAPL looks undervalued with meaningful DCF upside.',
    valuation_verdict: 'undervalued',
    upside_pct: 25,
    assessment_confidence: 'high',
    already_held: false,
    current_weight_pct: 0,
    concentration_limit_pct: 15,
    headroom_pct: 15,
    suitability_factors: [{ name: 'valuation', detail: 'Undervalued with 25% upside', favorable: true }],
    key_risks: ['A DCF is sensitive to its assumptions.'],
    disclaimers: ['Advisory only and not investment advice; you make the final decision.']
  }
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('EquityRecommendationCard', () => {
  it('renders direction, upside, rationale, risks, and disclaimers', () => {
    render(EquityRecommendationCard, { props: { result: fixture } });
    expect(screen.getByTestId('equity-direction').textContent?.toLowerCase()).toContain('buy');
    expect(screen.getByTestId('equity-upside').textContent).toContain('+25.0%');
    expect(screen.getByTestId('equity-rationale').textContent).toContain('undervalued');
    expect(screen.getByTestId('equity-risk').textContent).toContain('DCF');
    expect(screen.getByTestId('equity-disclaimer').textContent).toContain('not investment advice');
    expect(screen.getByTestId('equity-factor').textContent).toContain('25% upside');
  });
});

describe('EquityAnalyzer', () => {
  it('analyzes a ticker and renders the recommendation card', async () => {
    const spy = vi.spyOn(apiService, 'analyzeEquity').mockResolvedValue(fixture);
    render(EquityAnalyzer);

    await fireEvent.update(screen.getByTestId('input-equity-ticker'), 'aapl');
    await fireEvent.click(screen.getByTestId('btn-analyze-equity'));

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith('AAPL', 'demo_user');
      expect(screen.getByTestId('equity-recommendation-card')).toBeDefined();
    });
  });

  it('surfaces an error when the analysis fails', async () => {
    vi.spyOn(apiService, 'analyzeEquity').mockRejectedValue(new Error('No SEC CIK found for ticker'));
    render(EquityAnalyzer);

    await fireEvent.update(screen.getByTestId('input-equity-ticker'), 'ZZZZ');
    await fireEvent.click(screen.getByTestId('btn-analyze-equity'));

    await waitFor(() => {
      expect(screen.getByTestId('equity-analyzer-error').textContent).toContain('No SEC CIK');
    });
  });
});
