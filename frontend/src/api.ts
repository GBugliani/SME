export type User = { id: number; email: string; nome: string; administrador: boolean; perfil: string; perfil_id: number | null; ativo: boolean; permissoes: string[] };
export type SourceInput = {
  nome: string; tipo: string; url: string; ativa: boolean; periodo_movel?:boolean; url_coleta?:string;
  recorte_tipo: string; recorte_nome: string; recorte_codigo: string; recorte_uf: string;
};
export type CollectionRun = { id: number; status: 'executando' | 'sucesso' | 'vazia' | 'erro'; iniciada_em: string; finalizada_em: string | null; mensagem: string; quantidade_registros: number; repetida: boolean; origem: string };
export type Integration = {codigo:string; provedor:string; publicador:string; base_original:string; agravo:string; agravo_nome:string; indicador_nome:string; definicao:string; base_temporal:string; base_territorial:string; unidade:string; frequencia:string; documentacao:string; municipios:'SP'|string[];codigos_com_dados?:string[]};
export type Source = SourceInput & { indicador?:string; integracao?:Integration|null; id: number; ultima_coleta_em: string | null; processamento?: { status:string; mensagem:string; registros:number } | null; coleta_disponivel: boolean; ultima_execucao: CollectionRun | null };
export type SourcePage = { sources: Source[]; count: number; page: number; pages: number; coleta_realizada: boolean; falhas_processamento?: number };

export class ApiError extends Error {
  constructor(message: string, public status: number, public fields?: Record<string, string[]>) { super(message); }
}

let csrfToken = '';
export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (method !== 'GET') {
    if (!csrfToken) {
      const token = await api<{ csrfToken: string }>('/auth/csrf/');
      csrfToken = token.csrfToken;
    }
    headers['X-CSRFToken'] = csrfToken;
    headers['Content-Type'] = 'application/json';
  }
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { method, headers, credentials: 'same-origin', body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError('Não foi possível conectar ao sistema. Verifique a conexão e tente novamente.', 0);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(data.error || 'Não foi possível concluir a solicitação.', response.status, data.fields);
  if (data.csrfToken) csrfToken = data.csrfToken;
  if (path === '/auth/logout/') csrfToken = '';
  return data as T;
}
