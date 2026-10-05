import { useEffect, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { api, ApiError, type User, type Source, type SourceInput, type SourcePage } from './api';
import './styles.css';

const emptySource: SourceInput = { nome: '', tipo: 'csv', url: '', ativa: true, recorte_tipo: 'municipio', recorte_nome: '', recorte_codigo: '', recorte_uf: 'SP' };
const describe = (error: unknown) => error instanceof Error ? error.message : 'Ocorreu um erro inesperado.';

function Brand() {
  return <div className="brand"><span className="brand-icon" aria-hidden="true">✳</span><span>SME<small>Monitoramento epidemiológico</small></span></div>;
}

function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const values = new FormData(event.currentTarget);
    try { const data = await api<{ user: User }>('/auth/login/', 'POST', { email: values.get('email'), password: values.get('password') }); onLogin(data.user); }
    catch (err) { setError(describe(err)); } finally { setBusy(false); }
  }
  return <main className="login-layout">
    <section className="login-story"><Brand /><div><span className="eyebrow light">VIGILÂNCIA EPIDEMIOLÓGICA MUNICIPAL</span><h1>Informação para<br />cuidar do território.</h1><p>Um ponto de partida para acompanhar dados públicos de saúde e organizar o monitoramento do seu município.</p></div><div className="story-footer"><span className="status-dot" />Sistema de Monitoramento Epidemiológico</div></section>
    <section className="login-panel"><form onSubmit={submit} className="login-form"><span className="eyebrow">ACESSO AO SISTEMA</span><h2>Bem-vindo ao SME</h2><p className="muted">Entre com a conta autorizada pela sua equipe.</p>
      <label>E-mail<input name="email" type="email" autoComplete="username" placeholder="voce@instituicao.gov.br" required maxLength={254} /></label>
      <label>Senha<input name="password" type="password" autoComplete="current-password" placeholder="Sua senha" required maxLength={1024} /></label>
      {error && <div className="error" role="alert">{error}</div>}
      <button disabled={busy} type="submit">{busy ? 'Entrando…' : 'Entrar no sistema'}<span aria-hidden="true"> →</span></button>
      <p className="login-note">Precisa de acesso? Solicite uma conta ao administrador responsável.</p>
    </form><footer>SME · Dados públicos, cuidado local.</footer></section>
  </main>;
}

function SourceForm({ source, onSave, onCancel, onExpired }: { source?: Source; onSave: () => void; onCancel: () => void; onExpired: () => void }) {
  const [values, setValues] = useState<SourceInput>(source ?? emptySource);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [fields, setFields] = useState<Record<string, string[]>>({});
  function field(key: keyof SourceInput, value: string | boolean) { setValues(v => ({ ...v, [key]: value })); }
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setFields({});
    try { await api(source ? `/fontes/${source.id}/` : '/fontes/', source ? 'PUT' : 'POST', values); onSave(); }
    catch (err) {
      if (err instanceof ApiError && err.status === 401) { onExpired(); return; }
      setError(describe(err)); if (err instanceof ApiError) setFields(err.fields ?? {});
    } finally { setBusy(false); }
  }
  const hint = (key: string) => fields[key] && <span className="field-error" id={`error-${key}`}>{fields[key].join(' ')}</span>;
  const input = (key: keyof SourceInput, label: string, placeholder: string, maxLength: number, type = 'text') => <label>{label}<input type={type} value={String(values[key])} onChange={e => field(key, e.target.value)} placeholder={placeholder} maxLength={maxLength} required aria-invalid={Boolean(fields[key])} aria-describedby={fields[key] ? `error-${key}` : undefined} />{hint(key)}</label>;
  return <section className="card form-card"><div className="section-heading"><div><span className="eyebrow">CONFIGURAÇÃO</span><h2>{source ? 'Editar fonte' : 'Cadastrar fonte pública'}</h2></div><button className="secondary" onClick={onCancel} disabled={busy}>Cancelar</button></div>
    <p className="muted">Associe um endereço público ao território que será acompanhado. O cadastro ainda não executa a coleta.</p>
    <form onSubmit={submit}>
      <div className="form-grid">{input('nome', 'Nome da fonte', 'Ex.: Boletim municipal de dengue', 150)}<label>Formato<select value={values.tipo} onChange={e => field('tipo', e.target.value)}><option value="csv">CSV</option><option value="json">JSON / API</option></select>{hint('tipo')}</label></div>
      {input('url', 'Endereço HTTPS da fonte', 'https://', 2000, 'url')}
      <div className="form-grid"><label>Tipo de território<select value={values.recorte_tipo} onChange={e => { field('recorte_tipo', e.target.value); field('recorte_codigo', ''); }}><option value="municipio">Município</option><option value="regiao">Região</option></select>{hint('recorte_tipo')}</label>{input('recorte_nome', 'Nome do território', 'Ex.: São Paulo', 150)}</div>
      <div className="form-grid">{input('recorte_codigo', values.recorte_tipo === 'municipio' ? 'Código IBGE (7 dígitos)' : 'Código da região', values.recorte_tipo === 'municipio' ? '3550308' : 'Código na fonte de dados', 50)}<label>UF{values.recorte_tipo === 'regiao' && ' (opcional)'}<input value={values.recorte_uf} onChange={e => field('recorte_uf', e.target.value.toUpperCase())} maxLength={2} required={values.recorte_tipo === 'municipio'} aria-invalid={Boolean(fields.recorte_uf)} />{hint('recorte_uf')}</label></div>
      <label className="checkbox"><input type="checkbox" checked={values.ativa} onChange={e => field('ativa', e.target.checked)} />Habilitada para futura coleta</label>
      {error && <div className="error" role="alert">{error}{fields.__all__ && <p>{fields.__all__.join(' ')}</p>}</div>}
      <div className="form-actions"><button type="submit" disabled={busy}>{busy ? 'Salvando…' : 'Salvar fonte'}</button></div>
    </form>
  </section>;
}

function Workspace({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [tab, setTab] = useState('inicio');
  const [page, setPage] = useState<SourcePage>({ sources: [], count: 0, page: 1, pages: 1 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [editor, setEditor] = useState<Source | 'new' | null>(null);
  async function load(number = 1) {
    setLoading(true); setError('');
    try { setPage(await api<SourcePage>(`/fontes/?page=${number}`)); }
    catch (err) { if (err instanceof ApiError && err.status === 401) onLogout(); else setError(describe(err)); }
    finally { setLoading(false); }
  }
  useEffect(() => { if (user.administrador) void load(); }, []);
  async function signOut() {
    try { await api('/auth/logout/', 'POST'); onLogout(); }
    catch (err) { if (err instanceof ApiError && err.status === 401) onLogout(); else setError(describe(err)); }
  }
  return <div className="app-shell"><aside className="sidebar"><Brand /><p className="nav-label">ÁREA DE TRABALHO</p><nav aria-label="Navegação principal"><button className={tab === 'inicio' ? 'selected' : ''} onClick={() => { setTab('inicio'); setEditor(null); }}>◫ <span>Visão geral</span></button>{user.administrador && <button className={tab === 'fontes' ? 'selected' : ''} onClick={() => { setTab('fontes'); setSuccess(''); }}>▤ <span>Fontes de dados</span></button>}</nav><div className="sidebar-bottom"><span className="status-dot" />Vigilância municipal<small>Projeto SME · 2026</small></div></aside>
    <div className="main-area"><header className="topbar"><span>Ambiente de monitoramento</span><div className="account"><span className="avatar">{user.nome[0].toUpperCase()}</span><div>{user.nome}<small>{user.administrador ? 'Administrador' : 'Usuário'}</small></div><button className="secondary" onClick={signOut}>Sair</button></div></header>
      <main className="content"><div className="page-heading"><div><span className="eyebrow">SME / {tab === 'inicio' ? 'VISÃO GERAL' : 'ADMINISTRAÇÃO'}</span><h1>{tab === 'inicio' ? 'Seu território, em perspectiva.' : 'Fontes de dados'}</h1><p className="muted">{tab === 'inicio' ? 'Organize a base do acompanhamento epidemiológico da sua equipe.' : 'Gerencie a origem dos dados e os territórios monitorados.'}</p></div>{tab === 'fontes' && !editor && <button onClick={() => { setEditor('new'); setSuccess(''); }}>+ Cadastrar fonte</button>}</div>
      {error && <div className="error" role="alert">{error} {user.administrador && <button className="secondary" onClick={() => void load(page.page)}>Tentar novamente</button>}</div>}
      {success && <div className="success" role="status">{success}</div>}
      {tab === 'inicio' ? <><section className="welcome-card"><div><span className="eyebrow light">BASE DE MONITORAMENTO</span><h2>Comece pelas fontes.<br />Construa o acompanhamento.</h2><p>O acesso está configurado. O próximo passo é associar as fontes públicas aos municípios e regiões de interesse.</p>{user.administrador && <button className="white-button" onClick={() => setTab('fontes')}>Gerenciar fontes <span aria-hidden="true">↗</span></button>}</div><div className="territory-art" aria-hidden="true"><span>+</span><span>+</span><span>+</span><span>+</span><span>+</span><span>+</span></div></section>
        <div className="overview-grid"><section className="card"><span className="eyebrow">{user.administrador ? 'FONTES CADASTRADAS' : 'SEU ACESSO'}</span><strong className="metric">{user.administrador ? (loading ? '…' : error ? '—' : page.count) : 'Ativo'}</strong><p className="muted">{user.administrador ? 'Origens de dados configuradas pela equipe.' : 'Conta autorizada para o monitoramento.'}</p></section><section className="card next-card"><span className="eyebrow">SÉRIES EPIDEMIOLÓGICAS</span><h3>Aguardando integração de dados</h3><p className="muted">Os indicadores e gráficos serão disponibilizados após a implementação e validação da coleta. Ainda não há dados epidemiológicos neste ambiente.</p></section></div></>
      : editor ? <SourceForm key={editor === 'new' ? 'new' : editor.id} source={editor === 'new' ? undefined : editor} onCancel={() => setEditor(null)} onExpired={onLogout} onSave={() => { setEditor(null); setSuccess('Fonte salva com sucesso.'); void load(); }} />
      : <section className="card source-list"><div className="section-heading"><h2>Origens cadastradas</h2><span className="counter">{page.count} {page.count === 1 ? 'fonte' : 'fontes'}</span></div>{loading ? <p role="status">Carregando fontes…</p> : page.sources.length === 0 ? <div className="empty-state"><span className="empty-icon" aria-hidden="true">▤</span><h3>Nenhuma fonte cadastrada</h3><p>Adicione uma fonte pública e associe o território<br />para preparar o monitoramento.</p><button className="secondary" onClick={() => setEditor('new')}>Cadastrar primeira fonte</button></div> : <><div className="table-scroll"><table><thead><tr><th>Fonte / território</th><th>Formato</th><th>Situação</th><th>Última coleta</th><th><span className="sr-only">Ações</span></th></tr></thead><tbody>{page.sources.map(s => <tr key={s.id}><td><strong>{s.nome}</strong><small>{s.recorte_nome}{s.recorte_uf && ` / ${s.recorte_uf}`} · {s.recorte_codigo}</small><a href={s.url} target="_blank" rel="noreferrer">Ver fonte ↗</a></td><td>{s.tipo.toUpperCase()}</td><td><span className={`badge ${s.ativa ? '' : 'inactive'}`}>{s.ativa ? 'Habilitada' : 'Desabilitada'}</span></td><td>{s.ultima_coleta_em ? new Date(s.ultima_coleta_em).toLocaleString('pt-BR') : 'Não realizada'}</td><td><button className="secondary" aria-label={`Editar ${s.nome}`} onClick={() => { setEditor(s); setSuccess(''); }}>Editar</button></td></tr>)}</tbody></table></div><div className="pagination"><button className="secondary" disabled={page.page <= 1} onClick={() => void load(page.page - 1)}>Anterior</button><span>Página {page.page} de {page.pages}</span><button className="secondary" disabled={page.page >= page.pages} onClick={() => void load(page.page + 1)}>Próxima</button></div></>}
      </section>}
      <footer className="content-footer">Sistema de Monitoramento Epidemiológico<span>Fonte e atualização serão exibidas junto aos dados coletados.</span></footer></main>
    </div></div>;
}

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  async function restore() {
    setLoading(true); setError('');
    try { const data = await api<{ user: User }>('/auth/me/'); setUser(data.user); }
    catch (err) { if (!(err instanceof ApiError && err.status === 401)) setError(describe(err)); }
    finally { setLoading(false); }
  }
  useEffect(() => { void restore(); }, []);
  if (loading) return <main className="connection-screen" role="status"><Brand /><p>Conectando ao SME…</p></main>;
  if (error) return <main className="connection-screen"><Brand /><p role="alert">{error}</p><button onClick={() => void restore()}>Tentar novamente</button></main>;
  return user ? <Workspace user={user} onLogout={() => setUser(null)} /> : <Login onLogin={setUser} />;
}

createRoot(document.getElementById('root')!).render(<App />);
