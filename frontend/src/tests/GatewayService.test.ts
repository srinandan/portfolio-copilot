import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { GatewayService } from '../services/gateway';

describe('GatewayService', () => {
  let service: GatewayService;

  beforeEach(() => {
    service = new GatewayService('http://localhost:8080');
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('checkHealth returns ok on 200 response', async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok' })
    });

    const res = await service.checkHealth();
    expect(res).toEqual({ status: 'ok' });
    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8080/health');
  });

  it('checkHealth throws on non-200 response', async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 500
    });

    await expect(service.checkHealth()).rejects.toThrow('Health check failed with status 500');
  });

  it('checkAuth returns project id on success', async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({ project_id: 'test-project', message: 'ok' })
    });

    const res = await service.checkAuth();
    expect(res.project_id).toBe('test-project');
  });

  it('checkAuth throws on error status', async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 401
    });

    await expect(service.checkAuth()).rejects.toThrow('Auth check failed with status 401');
  });

  it('connectStream listens to message and close events', () => {
    const listeners: Record<string, ((e: any) => void)[]> = {};
    class MockEventSource {
      addEventListener(type: string, cb: (e: any) => void) {
        listeners[type] = listeners[type] || [];
        listeners[type].push(cb);
      }
      close = vi.fn();
    }
    vi.stubGlobal('EventSource', MockEventSource);

    const onMessage = vi.fn();
    const onClose = vi.fn();

    service.connectStream(onMessage, onClose);

    expect(listeners['message']).toBeDefined();
    expect(listeners['close']).toBeDefined();

    // Trigger message event with valid JSON
    listeners['message'][0]({ data: '{"time":"now","message":"hello"}' });
    expect(onMessage).toHaveBeenCalledWith({ time: 'now', message: 'hello' });

    // Trigger message event with non-JSON text
    listeners['message'][0]({ data: 'raw string' });
    expect(onMessage).toHaveBeenCalledWith({ message: 'raw string' });

    // Trigger close event
    listeners['close'][0]({});
    expect(onClose).toHaveBeenCalled();
  });

  it('getHoldings fetches holdings data from gateway', async () => {
    const mockHoldings = {
      total_value_usd: 1000000.0,
      cash_usd: 50000.0,
      as_of: '2023-10-24',
      positions: [
        {
          ticker: 'AAPL',
          name: 'Apple Inc.',
          asset_class: 'Equities (US)',
          quantity: 100,
          current_price_usd: 150.0,
          current_value_usd: 15000.0
        }
      ]
    };

    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => mockHoldings
    });

    const holdings = await service.getHoldings();
    expect(holdings.total_value_usd).toBe(1000000.0);
    expect(holdings.positions.length).toBe(1);
    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8080/api/holdings');
  });

  it('getHoldings throws on non-200 response', async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 500
    });

    await expect(service.getHoldings()).rejects.toThrow('Get holdings failed with status 500');
  });

  it('getDocuments fetches documents data from gateway', async () => {
    const mockDocs = [
      {
        id: 'doc-1',
        filename: 'Stmt.pdf',
        size_bytes: 1000,
        uploaded_at: '2023-10-24T00:00:00Z',
        status: 'SUCCESS'
      }
    ];

    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => mockDocs
    });

    const docs = await service.getDocuments();
    expect(docs.length).toBe(1);
    expect(docs[0].filename).toBe('Stmt.pdf');
    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8080/api/documents');
  });

  it('getDocuments throws on non-200 response', async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 500
    });

    await expect(service.getDocuments()).rejects.toThrow('Get documents failed with status 500');
  });

  it('getSpendingReport fetches spending report data from gateway', async () => {
    const mockReport = {
      user_id: 'usr_default',
      total_income_usd: 10000.0,
      total_outflow_usd: 8000.0,
      savings_rate: 0.2,
      reserve_months: 6.0,
      category_breakdown: [],
      anomalies: [],
      narrative_summary: 'Test summary'
    };

    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => mockReport
    });

    const report = await service.getSpendingReport(6);
    expect(report.savings_rate).toBe(0.2);
    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8080/api/spending_report?window_months=6');
  });

  it('getSpendingReport throws on non-200 response', async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 500
    });

    await expect(service.getSpendingReport()).rejects.toThrow('Get spending report failed with status 500');
  });

  it('getDriftReport fetches drift report data from gateway', async () => {
    const mockDrift = {
      as_of: '2023-10-24',
      has_active_ips: true,
      rebalance_recommended: false,
      unclassified_value_usd: 0.0,
      bands: []
    };

    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => mockDrift
    });

    const report = await service.getDriftReport();
    expect(report.rebalance_recommended).toBe(false);
    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8080/api/drift_report');
  });

  it('getDriftReport throws on non-200 response', async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 500
    });

    await expect(service.getDriftReport()).rejects.toThrow('Get drift report failed with status 500');
  });

  it('approveAction sends POST to approve endpoint', async () => {
    const mockAction = {
      action_id: 'act_100',
      session_id: 'sess-default',
      type: 'TRADE',
      status: 'APPROVED',
      rationale: 'Approved'
    };

    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => mockAction
    });

    const act = await service.approveAction('act_100');
    expect(act.status).toBe('APPROVED');
    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8080/api/proposed_actions/act_100/approve', {
      method: 'POST'
    });
  });

  it('approveAction throws on non-200 response', async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 500
    });

    await expect(service.approveAction('act_100')).rejects.toThrow('Approve action failed with status 500');
  });

  it('rejectAction sends POST to reject endpoint', async () => {
    const mockAction = {
      action_id: 'act_100',
      session_id: 'sess-default',
      type: 'TRADE',
      status: 'REJECTED',
      rationale: 'Rejected'
    };

    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => mockAction
    });

    const act = await service.rejectAction('act_100');
    expect(act.status).toBe('REJECTED');
    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8080/api/proposed_actions/act_100/reject', {
      method: 'POST'
    });
  });

  it('rejectAction throws on non-200 response', async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 500
    });

    await expect(service.rejectAction('act_100')).rejects.toThrow('Reject action failed with status 500');
  });

  it('triggerPlan posts plan request to /api/plan', async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      status: 200
    });

    const res = await service.triggerPlan({ user_id: 'user_1', message: 'start plan' });
    expect(res.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8080/api/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: 'user_1', message: 'start plan' })
    });
  });

  it('triggerPlan throws on error response', async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 503
    });

    await expect(service.triggerPlan({ user_id: 'user_1', message: 'start' })).rejects.toThrow(
      'Trigger plan failed with status 503'
    );
  });

  it('resumePlan posts payload to /api/plan/resume', async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      status: 200
    });

    const res = await service.resumePlan({
      user_id: 'user_1',
      session_id: 'sess_1',
      invocation_id: 'inv_1',
      interrupt_id: 'int_1',
      payload: { decision: 'approved' }
    });
    expect(res.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8080/api/plan/resume', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: 'user_1',
        session_id: 'sess_1',
        invocation_id: 'inv_1',
        interrupt_id: 'int_1',
        payload: { decision: 'approved' }
      })
    });
  });

  it('resumePlan throws on error response', async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 400
    });

    await expect(
      service.resumePlan({
        user_id: 'user_1',
        session_id: 'sess_1',
        invocation_id: 'inv_1',
        interrupt_id: 'int_1',
        payload: {}
      })
    ).rejects.toThrow('Resume plan failed with status 400');
  });

  it('defaults to relative URLs so requests hit the frontend origin (never the gateway directly)', async () => {
    // Regression: an earlier build baked VITE_GATEWAY_URL into the bundle, and the browser
    // then called the gateway (or worse, http://localhost:8080) directly, bypassing the
    // frontend Go proxy that mints ID tokens. That must not happen — the constructor with
    // no args must produce a service that fetches relative paths.
    const service = new GatewayService();
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), { status: 200 })
    );

    await service.checkHealth();

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const calledURL = fetchSpy.mock.calls[0][0] as string;
    expect(calledURL).toBe('/health');
    expect(calledURL).not.toMatch(/^https?:\/\//);

    fetchSpy.mockRestore();
  });
});


