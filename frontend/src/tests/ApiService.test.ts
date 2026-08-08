import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiService } from '../services/api';

describe('ApiService', () => {
  let service: ApiService;

  beforeEach(() => {
    service = new ApiService('http://localhost:8080');
    vi.restoreAllMocks();
  });

  it('checkHealth calls /health and returns JSON when response is ok', async () => {
    const mockHealth = { status: 'ok' };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockHealth)
    });

    const result = await service.checkHealth();
    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/health');
    expect(result).toEqual(mockHealth);
  });

  it('checkHealth throws error when response is not ok', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500
    });

    await expect(service.checkHealth()).rejects.toThrow('Health check failed with status 500');
  });

  it('checkAuth calls /api/auth-check and returns JSON when response is ok', async () => {
    const mockAuth = { project_id: 'test-project', message: 'ADC is configured correctly.' };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockAuth)
    });

    const result = await service.checkAuth();
    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/api/auth-check');
    expect(result).toEqual(mockAuth);
  });

  it('checkAuth throws error when response is not ok', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401
    });

    await expect(service.checkAuth()).rejects.toThrow('Auth check failed with status 401');
  });

  it('connectStream creates EventSource and handles events', () => {
    const mockEventSource = {
      addEventListener: vi.fn(),
      close: vi.fn(),
      onerror: null
    };
    (globalThis as unknown as Record<string, unknown>).EventSource = vi.fn().mockReturnValue(mockEventSource);

    const onMessage = vi.fn();
    const onClose = vi.fn();
    const source = service.connectStream(onMessage, onClose);

    expect(globalThis.EventSource).toHaveBeenCalledWith('http://localhost:8080/api/stream');
    expect(source).toBe(mockEventSource);
    expect(mockEventSource.addEventListener).toHaveBeenCalledWith('message', expect.any(Function));
    expect(mockEventSource.addEventListener).toHaveBeenCalledWith('close', expect.any(Function));

    // Test message handler with valid JSON
    const messageCall = mockEventSource.addEventListener.mock.calls.find(call => call[0] === 'message');
    expect(messageCall).toBeDefined();
    const messageHandler = messageCall![1];
    messageHandler({ data: JSON.stringify({ message: 'test' }) });
    expect(onMessage).toHaveBeenCalledWith({ message: 'test' });

    // Test message handler with non-JSON
    messageHandler({ data: 'raw string' });
    expect(onMessage).toHaveBeenCalledWith({ message: 'raw string' });

    // Test close handler
    const closeCall = mockEventSource.addEventListener.mock.calls.find(call => call[0] === 'close');
    expect(closeCall).toBeDefined();
    const closeHandler = closeCall![1];
    closeHandler();
    expect(mockEventSource.close).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it('getHoldings fetches holdings data', async () => {
    const mockHoldings = {
      user_id: 'usr_test',
      as_of: '2026-08-01T00:00:00Z',
      positions: [],
      cash_usd: 1000,
      total_value_usd: 1000
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockHoldings)
    });

    const result = await service.getHoldings();
    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/api/holdings');
    expect(result).toEqual(mockHoldings);
  });

  it('getDocuments fetches document items', async () => {
    const mockDocs = [{ document_id: 'doc_1', title: 'Test Doc', doc_type: 'tax_return' }];
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDocs)
    });

    const result = await service.getDocuments();
    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/api/documents');
    expect(result).toEqual(mockDocs);
  });

  it('getSpendingReport fetches report with window query param', async () => {
    const mockReport = {
      report_id: 'rep_1',
      user_id: 'usr_test',
      analysis_window_months: 6,
      categories: [],
      recurring_subscriptions: [],
      total_recurring_monthly_usd: 0,
      generated_at: '2026-08-01T00:00:00Z'
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockReport)
    });

    const result = await service.getSpendingReport(6);
    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/api/spending_report?window_months=6');
    expect(result).toEqual(mockReport);
  });

  it('getDriftReport fetches drift report', async () => {
    const mockDrift = {
      drift_id: 'drift_1',
      user_id: 'usr_test',
      status: 'DRIFT_DETECTED',
      asset_classes: [],
      generated_at: '2026-08-01T00:00:00Z'
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDrift)
    });

    const result = await service.getDriftReport();
    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/api/drift_report');
    expect(result).toEqual(mockDrift);
  });

  it('triggerPlan posts plan payload to /api/plan', async () => {
    const mockResponse = { ok: true, status: 200 } as unknown as Response;
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

    const payload = { user_id: 'usr_1', message: 'Hello planner' };
    const res = await service.triggerPlan(payload);
    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/api/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    expect(res).toBe(mockResponse);
  });

  it('resumePlan posts resume payload to /api/plan/resume', async () => {
    const mockResponse = { ok: true, status: 200 } as unknown as Response;
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

    const payload = {
      user_id: 'usr_1',
      session_id: 'sess_1',
      invocation_id: 'inv_1',
      interrupt_id: 'int_1',
      payload: { decision: 'approved' }
    };
    const res = await service.resumePlan(payload);
    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/api/plan/resume', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    expect(res).toBe(mockResponse);
  });

  it('readSSEStream parses SSE data lines and calls onEvent', async () => {
    const sseText = 'data: {"event_id": "1", "message": "hello"}\n\ndata: {"event_id": "2", "kind": "hitl_approval_request"}\n\n';
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(sseText));
        controller.close();
      }
    });
    const mockResponse = new Response(stream);
    const events: any[] = [];
    const { readSSEStream } = await import('../services/api');

    await readSSEStream(mockResponse, (e) => events.push(e));
    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({ event_id: '1', message: 'hello' });
    expect(events[1]).toEqual({ event_id: '2', kind: 'hitl_approval_request' });
  });

  it('readSSEStream handles non-JSON raw strings and unreadable response', async () => {
    const sseText = 'data: raw plain message\n\n';
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(sseText));
        controller.close();
      }
    });
    const mockResponse = new Response(stream);
    const events: any[] = [];
    const { readSSEStream } = await import('../services/api');

    await readSSEStream(mockResponse, (e) => events.push(e));
    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ raw: 'raw plain message' });

    // Test with response having no body
    const emptyResponse = { body: null } as unknown as Response;
    await readSSEStream(emptyResponse, () => {});
  });

  it('streamPlan calls triggerPlan and streams events', async () => {
    const sseText = 'data: {"status": "in_progress"}\n\n';
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(sseText));
        controller.close();
      }
    });
    const mockResponse = new Response(stream, { status: 200 });
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

    const events: any[] = [];
    await service.streamPlan(
      { user_id: 'usr_test', message: 'test plan' },
      (e) => events.push(e)
    );

    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/api/plan', expect.any(Object));
    expect(events).toEqual([{ status: 'in_progress' }]);
  });

  it('streamPlanResume calls resumePlan and streams events', async () => {
    const sseText = 'data: {"status": "executed"}\n\n';
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(sseText));
        controller.close();
      }
    });
    const mockResponse = new Response(stream, { status: 200 });
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

    const events: any[] = [];
    await service.streamPlanResume(
      {
        user_id: 'usr_test',
        session_id: 'sess_1',
        invocation_id: 'inv_1',
        interrupt_id: 'int_1',
        payload: { decision: 'approve' }
      },
      (e) => events.push(e)
    );

    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/api/plan/resume', expect.any(Object));
    expect(events).toEqual([{ status: 'executed' }]);
  });
});
