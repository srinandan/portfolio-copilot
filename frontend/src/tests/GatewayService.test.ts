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

  it('returns scaffold holdings data', async () => {
    const holdings = await service.getHoldings();
    expect(holdings.total_value_usd).toBeGreaterThan(0);
    expect(holdings.positions.length).toBe(3);
  });

  it('returns scaffold documents data', async () => {
    const docs = await service.getDocuments();
    expect(docs.length).toBe(1);
    expect(docs[0].status).toBe('SUCCESS');
  });

  it('returns approved action on approveAction', async () => {
    const act = await service.approveAction('act_100');
    expect(act.status).toBe('APPROVED');
  });

  it('returns rejected action on rejectAction', async () => {
    const act = await service.rejectAction('act_100');
    expect(act.status).toBe('REJECTED');
  });
});
