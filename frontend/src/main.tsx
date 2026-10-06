import { useEffect, useRef, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { api, ApiError, type User, type Source, type SourceInput, type SourcePage, type CollectionRun } from './api';
import './styles.css';
import { saoPauloPath } from './territory';
import municipalities from './municipalities.json';
import smeLogo from './assets/sme-logo.png';

const emptySource: SourceInput = { nome: '', tipo: 'csv', url: '', ativa: true, recorte_tipo: 'municipio', recorte_nome: '', recorte_codigo: '', recorte_uf: 'SP' };
const describe = (error: unknown) => error instanceof Error ? error.message : 'Ocorreu um erro inesperado.';

function Brand() {
  return <div className="brand logo-brand"><svg width="0" height="0" aria-hidden="true"><defs><filter id="logo-background" colorInterpolationFilters="sRGB"><feColorMatrix type="matrix" values="1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 3 3 3 0 -0.8" /></filter></defs></svg><img src={smeLogo} alt="SME" /></div>;
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
    <section className="login-story"><div><span className="eyebrow">MONITORAMENTO</span><h1>Monitoramento epidemiológico</h1><p>Fontes públicas e dados epidemiológicos por município e região.</p></div><div className="login-map"><svg viewBox="-30 -30 780 500" role="img" aria-label="Contorno do estado de São Paulo"><path d={saoPauloPath} fill="#1c2b43" stroke="#668ad0" strokeWidth="1.5"/></svg><span className="login-map-caption">São Paulo · SP</span></div></section>
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
    <p className="muted">Associe um endereço público ao território que será acompanhado. Após salvar uma fonte InfoDengue de dengue em um município de SP, use “Coletar agora” ou aguarde o agendamento diário.</p>
    <form onSubmit={submit}>
      <div className="form-grid">{input('nome', 'Nome da fonte', 'Ex.: Boletim municipal de dengue', 150)}<label>Formato<select value={values.tipo} onChange={e => field('tipo', e.target.value)}><option value="csv">CSV</option><option value="json">JSON / API</option></select>{hint('tipo')}</label></div>
      {input('url', 'Endereço HTTPS da fonte', 'https://', 2000, 'url')}
      <div className="form-grid"><label>Tipo de território<select value={values.recorte_tipo} onChange={e => { field('recorte_tipo', e.target.value); field('recorte_codigo', ''); }}><option value="municipio">Município</option><option value="regiao">Região</option></select>{hint('recorte_tipo')}</label>{input('recorte_nome', 'Nome do território', 'Ex.: São Paulo', 150)}</div>
      <div className="form-grid">{input('recorte_codigo', values.recorte_tipo === 'municipio' ? 'Código IBGE (7 dígitos)' : 'Código da região', values.recorte_tipo === 'municipio' ? '3550308' : 'Código na fonte de dados', 50)}<label>UF{values.recorte_tipo === 'regiao' && ' (opcional)'}<input value={values.recorte_uf} onChange={e => field('recorte_uf', e.target.value.toUpperCase())} maxLength={2} required={values.recorte_tipo === 'municipio'} aria-invalid={Boolean(fields.recorte_uf)} />{hint('recorte_uf')}</label></div>
      <label className="checkbox"><input type="checkbox" checked={values.ativa} onChange={e => field('ativa', e.target.checked)} />Habilitada para coleta</label>
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
  const [mapView, setMapView] = useState({ zoom: 0.8, pan: { x: 0, y: 0 } });
  const { zoom, pan } = mapView;
  const mapRef = useRef<SVGSVGElement>(null);
  const [hoveredCity, setHoveredCity] = useState<{ id: string; name: string; x: number; y: number } | null>(null);
  function changeZoom(factor: number, anchor = { x: 360, y: 220 }) {
    setMapView(view => {
      const next = Math.max(.6, Math.min(10, view.zoom * factor));
      const ratio = next / view.zoom;
      return { zoom: next, pan: { x: anchor.x - 360 - (anchor.x - 360 - view.pan.x) * ratio, y: anchor.y - 220 - (anchor.y - 220 - view.pan.y) * ratio } };
    });
  }
  useEffect(() => {
    const svg = mapRef.current;
    if (!svg || tab !== 'inicio') return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      const matrix = svg.getScreenCTM();
      if (!matrix) return;
      const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? window.innerHeight : 1);
      changeZoom(Math.exp(-Math.max(-160, Math.min(160, delta)) * .002), point);
    };
    svg.addEventListener('wheel', wheel, { passive: false });
    return () => svg.removeEventListener('wheel', wheel);
  }, [tab]);
  const drag = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);
  const [showDataFlow, setShowDataFlow] = useState(false);
  const [collecting, setCollecting] = useState<number | null>(null);
  const [collectionHistory, setCollectionHistory] = useState<{ source: Source; runs: CollectionRun[] } | null>(null);
  async function collect(source: Source) {
    setCollecting(source.id); setError(''); setSuccess('');
    try {
      const data = await api<{ execucao: CollectionRun }>(`/fontes/${source.id}/coletas/`, 'POST', {});
      setSuccess(data.execucao.status === 'vazia' ? `${source.nome}: ${data.execucao.mensagem}` : `${source.nome}: ${data.execucao.quantidade_registros} registros brutos coletados.${data.execucao.repetida ? ' Conteúdo já armazenado; sem duplicação.' : ''} Os indicadores ainda aguardam processamento.`);
    } catch (err) { if (err instanceof ApiError && err.status === 401) onLogout(); else setError(describe(err)); }
    finally { setCollecting(null); void load(page.page, false); }
  }
  async function showHistory(source: Source) {
    try { const data = await api<{ execucoes: CollectionRun[] }>(`/fontes/${source.id}/coletas/`); setCollectionHistory({ source, runs: data.execucoes }); }
    catch (err) { if (err instanceof ApiError && err.status === 401) onLogout(); else setError(describe(err)); }
  }
  async function load(number = 1, clearError = true) {
    setLoading(true); if (clearError) setError('');
    try { setPage(await api<SourcePage>(`/fontes/?page=${number}`)); }
    catch (err) { if (err instanceof ApiError && err.status === 401) onLogout(); else setError(describe(err)); }
    finally { setLoading(false); }
  }
  useEffect(() => { if (user.administrador) void load(); }, []);
  async function signOut() {
    try { await api('/auth/logout/', 'POST'); onLogout(); }
    catch (err) { if (err instanceof ApiError && err.status === 401) onLogout(); else setError(describe(err)); }
  }
  return <div className={`app-shell ${tab === 'inicio' ? 'monitoring-shell' : ''}`}>

    <header className="topbar"><Brand /><nav aria-label="Navegação principal"><button className={tab === 'inicio' ? 'selected' : ''} onClick={() => { setTab('inicio'); setEditor(null); }}>Monitoramento</button>{user.administrador && <button className={tab === 'fontes' ? 'selected' : ''} onClick={() => { setTab('fontes'); setSuccess(''); }}>Fontes de dados</button>}</nav><div className="header-actions"><div className="account"><span className="avatar" title={user.nome}>{user.nome[0].toUpperCase()}</span><button className="secondary" onClick={signOut}>Sair</button></div></div></header>
    <main className="content">
      {collectionHistory && <section className="card collection-history" aria-label="Histórico de coleta"><div className="section-heading"><h2>Coletas · {collectionHistory.source.nome}</h2><button className="secondary" onClick={() => setCollectionHistory(null)}>Fechar histórico</button></div>{collectionHistory.runs.length === 0 ? <p>Nenhuma coleta executada.</p> : <ul>{collectionHistory.runs.map(run => <li key={run.id}><strong>{run.status === 'sucesso' ? 'Concluída' : run.status === 'vazia' ? 'Sem registros' : run.status === 'erro' ? 'Falha' : 'Executando'} · {new Date(run.iniciada_em).toLocaleString('pt-BR')}</strong><p>{run.mensagem}</p><small>{run.quantidade_registros} registros · {run.origem === 'airflow' ? 'Agendada' : 'Manual'}{run.repetida ? ' · Conteúdo já armazenado' : ''}</small></li>)}</ul>}</section>}

      {error && <div className="error" role="alert">{error} {user.administrador && <button className="secondary" onClick={() => void load(page.page)}>Tentar novamente</button>}</div>}
      {success && <div className="success" role="status">{success}</div>}
      {tab === 'inicio' ? <>
      <div className="dashboard-heading"><div><span className="eyebrow">PAINEL TERRITORIAL</span><h1>Monitoramento epidemiológico</h1></div><span className="scope-pill">São Paulo · SP</span></div>
      <div className="dashboard-grid">
        <aside className="dashboard-left">
          <section className="card summary-card"><div className="section-heading"><span className="eyebrow">BASE DE MONITORAMENTO</span><span className="badge inactive">Em preparação</span></div><h2>Resumo do monitoramento</h2><div className="primary-metric"><strong>{user.administrador ? loading ? '…' : error ? '—' : String(page.count).padStart(2, '0') : '—'}</strong><span>fontes públicas<br />cadastradas</span></div><div className="metric-rule" /><dl className="status-list"><div><dt>Coleta</dt><dd>{page.sources.some(s => s.ultima_coleta_em) ? 'Dados brutos coletados' : 'Aguardando coleta'}</dd></div><div><dt>Indicadores</dt><dd>Não disponíveis</dd></div><div><dt>Seu perfil</dt><dd>{user.administrador ? 'Administrador' : 'Usuário'}</dd></div></dl>{user.administrador && <button className="text-button" onClick={() => setTab('fontes')}>Gerenciar fontes <span>↗</span></button>}</section>

        </aside>
        <section className="territory-panel" aria-label="Mapa de referência do estado de São Paulo"><div className="map-toolbar"><span className="map-tab">Território</span><span className="muted">Recorte de referência · SP</span><span className="map-legend"><i />Sem classificação epidemiológica</span></div><div className="map-stage"><div className="map-coordinate">23° S / 47° O <span>SUDESTE · BRASIL</span></div><svg ref={mapRef} className="interactive-map" viewBox="-30 -30 780 500" role="img" aria-labelledby="map-title map-description" onPointerDown={e => { if (e.button !== 0) return; e.currentTarget.setPointerCapture(e.pointerId); setHoveredCity(null); drag.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y }; }} onPointerMove={e => { if (!drag.current) return; const matrix = e.currentTarget.getScreenCTM(); if (!matrix) return; const inverse = matrix.inverse(); const start = new DOMPoint(drag.current.x, drag.current.y).matrixTransform(inverse); const current = new DOMPoint(e.clientX, e.clientY).matrixTransform(inverse); const nextPan = { x: drag.current.panX + current.x - start.x, y: drag.current.panY + current.y - start.y }; setMapView(view => ({ ...view, pan: nextPan })); }} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }} onLostPointerCapture={() => { drag.current = null; }}><title id="map-title">Contorno do estado de São Paulo</title><desc id="map-description">Mapa geográfico de referência, sem dados de casos ou classificação de risco.</desc><defs><linearGradient id="map-fill" x2="1" y2="1"><stop stopColor="#293b5c"/><stop offset="1" stopColor="#142238"/></linearGradient></defs><g transform={`translate(${pan.x} ${pan.y}) translate(360 220) scale(${zoom}) translate(-360 -220)`}><path d={saoPauloPath} fill="url(#map-fill)" stroke="#668ad0" strokeWidth="1.5"/>{municipalities.map(city => <path key={city.id} d={city.path} className={`municipality ${hoveredCity?.id === city.id ? 'highlighted' : ''}`} fill="transparent" stroke="#4a6286" strokeWidth=".65" onPointerMove={event => { if (drag.current) return; setHoveredCity({ id: city.id, name: city.name, x: Math.max(12, Math.min(window.innerWidth - 272, event.clientX + 16)), y: Math.max(12, Math.min(window.innerHeight - 140, event.clientY + 16)) }); }} onPointerLeave={() => setHoveredCity(null)}><title>{city.name} · IBGE {city.id}</title></path>)}</g></svg>{hoveredCity && <div className="municipality-tooltip" role="status" style={{ left: hoveredCity.x, top: hoveredCity.y }}><strong>{hoveredCity.name}</strong><span>São Paulo · IBGE {hoveredCity.id}</span><p>Dados epidemiológicos ainda não disponíveis.</p></div>}<div className="map-zoom"><button aria-label="Ampliar mapa" disabled={zoom >= 10} onClick={() => changeZoom(1.3)}>+</button><button aria-label="Reduzir mapa" disabled={zoom <= .6} onClick={() => changeZoom(1 / 1.3)}>−</button><button className="map-reset" aria-label="Restaurar posição e zoom do mapa" title="Restaurar mapa" onClick={() => { setMapView({ zoom: 0.8, pan: { x: 0, y: 0 } }); }}><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M8 3H3v5M16 3h5v5M3 16v5h5M21 16v5h-5"/><circle cx="12" cy="12" r="3"/></svg></button></div><div className="map-note"><span className="eyebrow">VISUALIZAÇÃO TERRITORIAL</span><strong>Indicadores ainda não disponíveis</strong><p>Os dados brutos coletados ainda precisam ser padronizados para exibir indicadores.</p></div></div><div className="map-bottom"><span>Malha territorial · IBGE</span><span>Referência geográfica, sem indicadores de risco</span></div></section>
        <aside className="dashboard-right"><section className="card"><div className="section-heading"><h3>Fontes cadastradas</h3><span className="counter">{user.administrador ? page.count : '—'}</span></div>{loading ? <p role="status" className="muted">Carregando fontes…</p> : !user.administrador ? <p className="muted">As fontes são configuradas pelo administrador da equipe.</p> : page.sources.length ? <><div className="source-feed">{page.sources.slice(0, 5).map(s => <div key={s.id}><span className={`source-dot ${s.ativa ? 'enabled' : ''}`} /><div><strong>{s.nome}</strong><small>{s.recorte_nome} · {s.recorte_uf || s.recorte_tipo}</small><span className="feed-status">{s.ativa ? 'Habilitada' : 'Desabilitada'} · {s.tipo.toUpperCase()}</span></div></div>)}</div>{page.count > 5 && <small>Exibindo {Math.min(5, page.sources.length)} de {page.count} fontes.</small>}</> : <div className="compact-empty"><span aria-hidden="true">↗</span><h3>Nenhuma fonte cadastrada</h3><p className="muted">Associe dados públicos a um município ou região.</p></div>}{user.administrador && <button className="text-button" onClick={() => { setTab('fontes'); setEditor('new'); }}>Cadastrar fonte <span>+</span></button>}</section><section className="card series-card"><span className="eyebrow">EVOLUÇÃO TEMPORAL</span><h3>Séries epidemiológicas</h3><div className="chart-empty"><span>Sem séries disponíveis</span></div><p className="muted">A curva será exibida após a coleta e validação dos dados.</p></section></aside>
      </div></>
      : <><div className="page-heading"><div><span className="eyebrow">ADMINISTRAÇÃO</span><h1>Fontes de dados</h1><p className="muted">Gerencie a origem dos dados e os territórios monitorados.</p></div><div className="source-heading-actions"><div className="flow-help"><button className="secondary help-button" aria-label="Fluxo dos dados" aria-expanded={showDataFlow} aria-controls="data-flow-panel" onClick={() => setShowDataFlow(v => !v)}>?</button>{showDataFlow && <section className="card pipeline-card" id="data-flow-panel" aria-label="Fluxo dos dados"><div className="section-heading"><span className="eyebrow">FLUXO DOS DADOS</span><button className="secondary flow-close" aria-label="Fechar fluxo dos dados" onClick={() => setShowDataFlow(false)}>×</button></div><h3>Etapas de integração</h3><ol><li className="current"><span>01</span><div><strong>Configurar fontes</strong><small>Cadastro disponível</small></div></li><li><span>02</span><div><strong>Coletar dados brutos</strong><small>Agendamento diário · 06h</small></div></li><li><span>03</span><div><strong>Acompanhar indicadores</strong><small>Aguardando dados validados</small></div></li></ol></section>}</div>{!editor && <button onClick={() => { setEditor('new'); setSuccess(''); }}>+ Cadastrar fonte</button>}</div></div>{editor ?
 <SourceForm key={editor === 'new' ? 'new' : editor.id} source={editor === 'new' ? undefined : editor} onCancel={() => setEditor(null)} onExpired={onLogout} onSave={() => { setEditor(null); setSuccess('Fonte salva com sucesso.'); void load(); }} />
      : <section className="card source-list"><div className="section-heading"><h2>Origens cadastradas</h2><span className="counter">{page.count} {page.count === 1 ? 'fonte' : 'fontes'}</span></div>{loading ? <p role="status">Carregando fontes…</p> : page.sources.length === 0 ? <div className="empty-state"><span className="empty-icon" aria-hidden="true">▤</span><h3>Nenhuma fonte cadastrada</h3><p>Adicione uma fonte pública e associe o território<br />para preparar o monitoramento.</p><button className="secondary" onClick={() => setEditor('new')}>Cadastrar primeira fonte</button></div> : <><div className="table-scroll"><table><thead><tr><th>Fonte / território</th><th>Formato</th><th>Situação</th><th>Última coleta</th><th><span className="sr-only">Ações</span></th></tr></thead><tbody>{page.sources.map(s => <tr key={s.id}><td><strong>{s.nome}</strong><small>{s.recorte_nome}{s.recorte_uf && ` / ${s.recorte_uf}`} · {s.recorte_codigo}</small><a href={s.url} target="_blank" rel="noreferrer">Ver fonte ↗</a></td><td>{s.tipo.toUpperCase()}</td><td><span className={`badge ${s.ativa ? '' : 'inactive'}`}>{s.ativa ? 'Habilitada' : 'Desabilitada'}</span></td><td>{s.ultima_coleta_em ? new Date(s.ultima_coleta_em).toLocaleString('pt-BR') : 'Não realizada'}{s.ultima_execucao && <small>{s.ultima_execucao.status === 'erro' ? 'Última tentativa falhou' : s.ultima_execucao.status === 'executando' ? 'Coleta em execução' : `${s.ultima_execucao.quantidade_registros} registros brutos`}</small>}</td><td><div className="source-actions">{s.coleta_disponivel && <button className="secondary" disabled={collecting !== null} onClick={() => void collect(s)}>{collecting === s.id ? 'Coletando…' : 'Coletar agora'}</button>}<button className="secondary" onClick={() => void showHistory(s)}>Histórico</button><button className="secondary" aria-label={`Editar ${s.nome}`} onClick={() => { setEditor(s); setSuccess(''); }}>Editar</button></div></td></tr>)}</tbody></table></div><div className="pagination"><button className="secondary" disabled={page.page <= 1} onClick={() => void load(page.page - 1)}>Anterior</button><span>Página {page.page} de {page.pages}</span><button className="secondary" disabled={page.page >= page.pages} onClick={() => void load(page.page + 1)}>Próxima</button></div></>}
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
