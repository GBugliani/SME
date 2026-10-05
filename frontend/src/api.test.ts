import { afterEach, describe, expect, it, vi } from 'vitest';

afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); });
describe('Sessão e API', () => {
  it('obtém CSRF, renova após login e nunca armazena a senha no navegador', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(Response.json({ csrfToken: 'initial' }))
      .mockResolvedValueOnce(Response.json({ user: { email: 'test@example.org' }, csrfToken: 'rotated' }))
      .mockResolvedValueOnce(Response.json({ ok: true }));
    vi.stubGlobal('fetch', fetchMock);
    const { api } = await import('./api');
    await api('/auth/login/', 'POST', { email: 'test@example.org', password: 'test-only' });
    expect(fetchMock.mock.calls[1][1].headers['X-CSRFToken']).toBe('initial');
    await api('/auth/logout/', 'POST');
    expect(fetchMock.mock.calls[2][1].headers['X-CSRFToken']).toBe('rotated');
    expect(fetchMock.mock.calls[1][1].credentials).toBe('same-origin');
  });
  it('preserva status e erros de validação para a interface', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ error: 'Inválido', fields: { url: ['Use HTTPS'] } }, { status: 400 })));
    const { api } = await import('./api');
    await expect(api('/fontes/')).rejects.toMatchObject({ status: 400, fields: { url: ['Use HTTPS'] } });
  });
  it('distingue falha de conexão de credenciais inválidas', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Network error')));
    const { api } = await import('./api');
    await expect(api('/auth/me/')).rejects.toMatchObject({ status: 0 });
  });
});
