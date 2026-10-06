import { useEffect, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { api, ApiError, type User, type Source, type SourceInput, type SourcePage } from './api';
import './styles.css';
import { saoPauloPath } from './territory';

const emptySource: SourceInput = { nome: '', tipo: 'csv', url: '', ativa: true, recorte_tipo: 'municipio', recorte_nome: '', recorte_codigo: '', recorte_uf: 'SP' };
const describe = (error: unknown) => error instanceof Error ? error.message : 'Ocorreu um erro inesperado.';

function Brand() {
  return <div className="brand">SME</div>;
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
  return <div className="login-shell"><header className="topbar"><Brand /></header><main className="login-layout">
    <section className="login-story"><div><span className="eyebrow">MONITORAMENTO</span><h1>Monitoramento epidemiológico</h1><p>Fontes públicas e dados epidemiológicos por município e região.</p></div><div className="login-map"><svg viewBox="-30 -30 780 500" role="img" aria-label="Contorno do estado de São Paulo"><path d={saoPauloPath} fill="#1c2b43" stroke="#668ad0" strokeWidth="1.5"/><text x="320" y="220" className="map-state">SP</text><text x="320" y="250" className="map-state-caption">SÃO PAULO</text></svg><span className="login-map-caption">São Paulo · SP</span></div></section>
    <section className="login-panel"><form onSubmit={submit} className="login-form"><span className="eyebrow">ACESSO AO SISTEMA</span><h2>Entrar no SME</h2><p className="muted">Informe seu e-mail e senha.</p>
      <label>E-mail<input name="email" type="email" autoComplete="username" placeholder="voce@instituicao.gov.br" required maxLength={254} /></label>
      <label>Senha<input name="password" type="password" autoComplete="current-password" placeholder="Sua senha" required maxLength={1024} /></label>
      {error && <div className="error" role="alert">{error}</div>}
      <button disabled={busy} type="submit">{busy ? 'Entrando…' : 'Entrar no sistema'}<span aria-hidden="true"> →</span></button>
      <p className="login-note">Para solicitar acesso, contate o administrador.</p>
    </form></section>
  </main></div>;
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
  const [zoom, setZoom] = useState(1);
  const [showDataFlow, setShowDataFlow] = useState(false);
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
  return <div className="app-shell">

    <header className="topbar"><div className="brand">SME</div><nav aria-label="Navegação principal"><button className={tab === 'inicio' ? 'selected' : ''} onClick={() => { setTab('inicio'); setEditor(null); }}>Monitoramento</button>{user.administrador && <button className={tab === 'fontes' ? 'selected' : ''} onClick={() => { setTab('fontes'); setSuccess(''); }}>Fontes de dados</button>}</nav><div className="header-actions"><div className="account"><span className="avatar" title={user.nome}>{user.nome[0].toUpperCase()}</span><button className="secondary" onClick={signOut}>Sair</button></div></div></header>
    <main className="content">
      {error && <div className="error" role="alert">{error} {user.administrador && <button className="secondary" onClick={() => void load(page.page)}>Tentar novamente</button>}</div>}
      {success && <div className="success" role="status">{success}</div>}
      {tab === 'inicio' ? <>
      <div className="dashboard-heading"><div><span className="eyebrow">PAINEL TERRITORIAL</span><h1>Monitoramento epidemiológico</h1></div><span className="scope-pill">São Paulo · SP</span></div>
      <div className="dashboard-grid">
        <aside className="dashboard-left">
          <section className="card summary-card"><div className="section-heading"><span className="eyebrow">BASE DE MONITORAMENTO</span><span className="badge inactive">Em preparação</span></div><h2>Resumo do monitoramento</h2><div className="primary-metric"><strong>{user.administrador ? loading ? '…' : error ? '—' : String(page.count).padStart(2, '0') : '—'}</strong><span>fontes públicas<br />cadastradas</span></div><div className="metric-rule" /><dl className="status-list"><div><dt>Coleta</dt><dd>Aguardando integração</dd></div><div><dt>Indicadores</dt><dd>Não disponíveis</dd></div><div><dt>Seu perfil</dt><dd>{user.administrador ? 'Administrador' : 'Usuário'}</dd></div></dl>{user.administrador && <button className="text-button" onClick={() => setTab('fontes')}>Gerenciar fontes <span>↗</span></button>}</section>

        </aside>
        <section className="territory-panel" aria-label="Mapa de referência do estado de São Paulo"><div className="map-toolbar"><span className="map-tab">Território</span><span className="muted">Recorte de referência · SP</span><span className="map-legend"><i />Sem classificação epidemiológica</span></div><div className="map-stage"><div className="map-coordinate">23° S / 47° O <span>SUDESTE · BRASIL</span></div><svg viewBox="-30 -30 780 500" role="img" aria-labelledby="map-title map-description"><title id="map-title">Contorno do estado de São Paulo</title><desc id="map-description">Mapa geográfico de referência, sem dados de casos ou classificação de risco.</desc><defs><pattern id="map-grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="#86a9ee" strokeOpacity=".12" strokeWidth=".7" /></pattern><linearGradient id="map-fill" x2="1" y2="1"><stop stopColor="#293b5c"/><stop offset="1" stopColor="#142238"/></linearGradient></defs><g transform={`translate(360 220) scale(${zoom}) translate(-360 -220)`}><path d={saoPauloPath} fill="url(#map-fill)" stroke="#668ad0" strokeWidth="1.5"/><path d={saoPauloPath} fill="url(#map-grid)"/><text x="320" y="220" className="map-state">SP</text><text x="320" y="246" className="map-state-caption">SÃO PAULO</text></g></svg><div className="map-zoom"><button aria-label="Ampliar mapa" disabled={zoom >= 1.6} onClick={() => setZoom(z => Math.min(1.6, z + .2))}>+</button><button aria-label="Reduzir mapa" disabled={zoom <= 1} onClick={() => setZoom(z => Math.max(1, z - .2))}>−</button></div><div className="map-note"><span className="eyebrow">VISUALIZAÇÃO TERRITORIAL</span><strong>Dados ainda não disponíveis</strong><p>A distribuição de casos depende da coleta e validação dos dados.</p></div></div><div className="map-bottom"><span>Malha territorial · IBGE</span><span>Referência geográfica, sem indicadores de risco</span></div></section>
        <aside className="dashboard-right"><section className="card"><div className="section-heading"><h3>Fontes cadastradas</h3><span className="counter">{user.administrador ? page.count : '—'}</span></div>{loading ? <p role="status" className="muted">Carregando fontes…</p> : !user.administrador ? <p className="muted">As fontes são configuradas pelo administrador da equipe.</p> : page.sources.length ? <><div className="source-feed">{page.sources.slice(0, 5).map(s => <div key={s.id}><span className={`source-dot ${s.ativa ? 'enabled' : ''}`} /><div><strong>{s.nome}</strong><small>{s.recorte_nome} · {s.recorte_uf || s.recorte_tipo}</small><span className="feed-status">{s.ativa ? 'Habilitada' : 'Desabilitada'} · {s.tipo.toUpperCase()}</span></div></div>)}</div>{page.count > 5 && <small>Exibindo {Math.min(5, page.sources.length)} de {page.count} fontes.</small>}</> : <div className="compact-empty"><span aria-hidden="true">↗</span><h3>Nenhuma fonte cadastrada</h3><p className="muted">Associe dados públicos a um município ou região.</p></div>}{user.administrador && <button className="text-button" onClick={() => { setTab('fontes'); setEditor('new'); }}>Cadastrar fonte <span>+</span></button>}</section><section className="card series-card"><span className="eyebrow">EVOLUÇÃO TEMPORAL</span><h3>Séries epidemiológicas</h3><div className="chart-empty"><span>Sem séries disponíveis</span></div><p className="muted">A curva será exibida após a coleta e validação dos dados.</p></section></aside>
      </div></>
      : <><div className="page-heading"><div><span className="eyebrow">ADMINISTRAÇÃO</span><h1>Fontes de dados</h1><p className="muted">Gerencie a origem dos dados e os territórios monitorados.</p></div><div className="source-heading-actions"><div className="flow-help"><button className="secondary help-button" aria-label="Fluxo dos dados" aria-expanded={showDataFlow} aria-controls="data-flow-panel" onClick={() => setShowDataFlow(v => !v)}>?</button>{showDataFlow && <section className="card pipeline-card" id="data-flow-panel" aria-label="Fluxo dos dados"><div className="section-heading"><span className="eyebrow">FLUXO DOS DADOS</span><button className="secondary flow-close" aria-label="Fechar fluxo dos dados" onClick={() => setShowDataFlow(false)}>×</button></div><h3>Etapas de integração</h3><ol><li className="current"><span>01</span><div><strong>Configurar fontes</strong><small>Cadastro disponível</small></div></li><li><span>02</span><div><strong>Coletar e validar</strong><small>Próxima etapa de integração</small></div></li><li><span>03</span><div><strong>Acompanhar indicadores</strong><small>Aguardando dados validados</small></div></li></ol></section>}</div>{!editor && <button onClick={() => { setEditor('new'); setSuccess(''); }}>+ Cadastrar fonte</button>}</div></div>{editor ?
 <SourceForm key={editor === 'new' ? 'new' : editor.id} source={editor === 'new' ? undefined : editor} onCancel={() => setEditor(null)} onExpired={onLogout} onSave={() => { setEditor(null); setSuccess('Fonte salva com sucesso.'); void load(); }} />
      : <section className="card source-list"><div className="section-heading"><h2>Origens cadastradas</h2><span className="counter">{page.count} {page.count === 1 ? 'fonte' : 'fontes'}</span></div>{loading ? <p role="status">Carregando fontes…</p> : page.sources.length === 0 ? <div className="empty-state"><span className="empty-icon" aria-hidden="true">▤</span><h3>Nenhuma fonte cadastrada</h3><p>Adicione uma fonte pública e associe o território<br />para preparar o monitoramento.</p><button className="secondary" onClick={() => setEditor('new')}>Cadastrar primeira fonte</button></div> : <><div className="table-scroll"><table><thead><tr><th>Fonte / território</th><th>Formato</th><th>Situação</th><th>Última coleta</th><th><span className="sr-only">Ações</span></th></tr></thead><tbody>{page.sources.map(s => <tr key={s.id}><td><strong>{s.nome}</strong><small>{s.recorte_nome}{s.recorte_uf && ` / ${s.recorte_uf}`} · {s.recorte_codigo}</small><a href={s.url} target="_blank" rel="noreferrer">Ver fonte ↗</a></td><td>{s.tipo.toUpperCase()}</td><td><span className={`badge ${s.ativa ? '' : 'inactive'}`}>{s.ativa ? 'Habilitada' : 'Desabilitada'}</span></td><td>{s.ultima_coleta_em ? new Date(s.ultima_coleta_em).toLocaleString('pt-BR') : 'Não realizada'}</td><td><button className="secondary" aria-label={`Editar ${s.nome}`} onClick={() => { setEditor(s); setSuccess(''); }}>Editar</button></td></tr>)}</tbody></table></div><div className="pagination"><button className="secondary" disabled={page.page <= 1} onClick={() => void load(page.page - 1)}>Anterior</button><span>Página {page.page} de {page.pages}</span><button className="secondary" disabled={page.page >= page.pages} onClick={() => void load(page.page + 1)}>Próxima</button></div></>}
      </section>}</>}
      </main></div>;

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








