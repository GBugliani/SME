import {ActionIcon} from './action-icon';
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { api, ApiError, type User, type Source, type SourceInput, type SourcePage, type CollectionRun, type Integration } from './api';
import './styles.css';
import { IndicatorFilters, SeriesChart, type Indicators, type IndicatorOptions, type MapSelection, type MapSignal } from './monitoring';
import {MapCityPicker, availableCityIntegrations, type PickedCity} from './map-city-picker';
import {MapTourPreview} from './map-tour-preview';
import {MapRegionLabels, buildMapRegions, getIntermediateRegionIndex, intermediateRegions} from './map-regions';
import {exactDecimal} from './number-format';
import { saoPauloPath } from './territory';
import smeLogo from './assets/sme-logo.webp';
import immediateRegions from './regions.json';
import {Notice,useTimedMessage} from './notifications';
import {SourceFeed} from './source-feed';
import {territoryLabel,sourcePeriodLabel} from './source-labels';
import {AssistedSourceForm,infoDengueParams} from './source-setup';
import {AccountMenu} from './account-menu';
import {Administration} from './administration';
import {ExportData} from './export-data';
import {AlertCenter} from './alerts';
import {TerritoryComparison} from './comparison';
import {DataQuality} from './data-quality';
import {HelpPage} from './help';
import {PasswordInput} from './password-input';
import {CompactOverview, CompactRecent, CompactQuality, CompactOrigin, CompactSeries, CompactSources} from './dashboard-summary';
type Municipality = { id: string; name: string; path: string };

const emptySource: SourceInput = { nome: '', tipo: 'csv', url: '', ativa: true, recorte_tipo: 'municipio', recorte_nome: '', recorte_codigo: '', recorte_uf: 'SP' };
const describe = (error: unknown) => error instanceof Error ? error.message : 'Ocorreu um erro inesperado.';

function Brand({onClick}:{onClick?:()=>void}) {
  const logo=<><svg width="0" height="0" aria-hidden="true"><defs><filter id="logo-background" colorInterpolationFilters="sRGB"><feColorMatrix type="matrix" values="1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 3 3 3 0 -0.8" /></filter></defs></svg><img src={smeLogo} alt="SME" /></>;
  return onClick?<button type="button" className="brand logo-brand brand-button" onClick={onClick} aria-label="Ir para o monitoramento" title="Ir para o monitoramento">{logo}</button>:<div className="brand logo-brand">{logo}</div>;
}

function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useTimedMessage();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const values = new FormData(event.currentTarget);
    try { const data = await api<{ user: User }>('/auth/login/', 'POST', { email: values.get('email'), password: values.get('password') }); onLogin(data.user); }
    catch (err) { setError(describe(err)); } finally { setBusy(false); }
  }
  return <div className="login-shell"><header className="topbar"><Brand /></header><main className="login-layout">
    <section className="login-story"><div><span className="eyebrow">MONITORAMENTO</span><h1>Monitoramento epidemiológico</h1><p>Fontes públicas e dados epidemiológicos por município e região.</p></div><div className="login-map"><svg viewBox="-30 -30 780 500" role="img" aria-label="Contorno do estado de São Paulo"><path d={saoPauloPath} fill="#1c2b43" stroke="#668ad0" strokeWidth="1.5"/></svg><span className="login-map-caption">São Paulo · SP</span></div></section>
    <section className="login-panel"><form onSubmit={submit} className="login-form"><span className="eyebrow">ACESSO AO SISTEMA</span><h2>Entrar no SME</h2><p className="muted">Informe seu e-mail e senha.</p>
      <label>E-mail<input name="email" type="email" autoComplete="username" required maxLength={254} /></label>
      <label>Senha<PasswordInput id="login-password" name="password" autoComplete="current-password" required maxLength={1024}/></label>
      <Notice message={error}/>
      <button disabled={busy} type="submit" data-icon="arrowRight"><ActionIcon name="arrowRight"/>{busy ? 'Entrando…' : 'Entrar no sistema'}</button>
      <p className="login-note">Para solicitar acesso ou redefinir sua senha, contate o administrador.</p>
    </form></section>
  </main></div>;
}

function SourceForm({ source, onSave, onCancel, onExpired }: { source?: Source; onSave: () => void; onCancel: () => void; onExpired: () => void }) {
  const [manual,setManual]=useState(Boolean(source&&!source.integracao&&!infoDengueParams(source)));
  const [values, setValues] = useState<SourceInput>(source ?? emptySource);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useTimedMessage();
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
  if(!manual)return <AssistedSourceForm source={source} onSave={onSave} onCancel={onCancel} onExpired={onExpired} onManual={()=>setManual(true)}/>;
  return <section className="card form-card"><div className="section-heading"><div><span className="eyebrow">CONFIGURAÇÃO</span><h2>{source ? 'Editar fonte' : 'Cadastrar fonte pública'}</h2></div><button className="secondary" onClick={onCancel} disabled={busy} data-icon="close"><ActionIcon name="close"/>Cancelar</button></div>
    <p className="muted">Associe um endereço público ao território que será acompanhado. A coleta automática depende de uma integração compatível. URLs de outros provedores podem ser cadastradas como referência, mas não serão coletadas automaticamente.</p>
    <form onSubmit={submit}>
      <div className="form-grid">{input('nome', 'Nome da fonte', 'Ex.: Boletim municipal de dengue', 150)}<label>Formato<select value={values.tipo} onChange={e => field('tipo', e.target.value)}><option value="csv">CSV</option><option value="json">JSON / API</option><option value="xlsx">Excel</option></select>{hint('tipo')}</label></div>
      {input('url', 'Endereço HTTPS da fonte', 'https://', 2000, 'url')}
      <div className="form-grid"><label>Tipo de território<select value={values.recorte_tipo} onChange={e => { field('recorte_tipo', e.target.value); field('recorte_codigo', ''); }}><option value="municipio">Município</option><option value="regiao">Região</option></select>{hint('recorte_tipo')}</label>{input('recorte_nome', 'Nome do território', 'Ex.: São Paulo', 150)}</div>
      <div className="form-grid">{input('recorte_codigo', values.recorte_tipo === 'municipio' ? 'Código IBGE (7 dígitos)' : 'Código da região', values.recorte_tipo === 'municipio' ? '3550308' : 'Código na fonte de dados', 50)}<label>UF{values.recorte_tipo === 'regiao' && ' (opcional)'}<input value={values.recorte_uf} onChange={e => field('recorte_uf', e.target.value.toUpperCase())} maxLength={2} required={values.recorte_tipo === 'municipio'} aria-invalid={Boolean(fields.recorte_uf)} />{hint('recorte_uf')}</label></div>
      <label className="checkbox"><input type="checkbox" checked={values.ativa} onChange={e => field('ativa', e.target.checked)} />Habilitada para coleta</label>
      <Notice message={error}>{fields.__all__ && <p>{fields.__all__.join(' ')}</p>}</Notice>
      <div className="form-actions"><button type="submit" disabled={busy} data-icon="save"><ActionIcon name="save"/>{busy ? 'Salvando…' : 'Salvar fonte'}</button></div>
    </form>
  </section>;
}

function Workspace({ user, onLogout, onUserChanged }: { user: User; onLogout: () => void; onUserChanged: (user:User)=>void }) {
  const canSources = user.permissoes.includes("gerenciar_fontes");
  const canCollect = user.permissoes.includes("coletar_dados");
  const [tab, setTab] = useState('inicio');
  const currentTab=useRef(tab);currentTab.current=tab;
  const contentRef=useRef<HTMLElement>(null);
  const [advancedPanels,setAdvancedPanels] = useState(false);
  const [indicators, setIndicators] = useState<Indicators|null>(null);
  const hasSelectedMunicipality=indicators?.territorio.tipo==='municipio';
  const showDetailedPanels=Boolean(hasSelectedMunicipality&&advancedPanels);
  useLayoutEffect(()=>{if(tab==='inicio'&&!hasSelectedMunicipality)window.scrollTo(0,0);},[tab,hasSelectedMunicipality]);
  const [mapControlsVisible,setMapControlsVisible]=useState(true);
  const [mobilePanelHintVisible,setMobilePanelHintVisible]=useState(true);
  useLayoutEffect(()=>{
    if(tab!=='inicio')return;
    const panel=contentRef.current?.querySelector<HTMLElement>('.territory-panel');
    const comparison=contentRef.current?.querySelector<HTMLElement>('.comparison-panel');
    const hint=contentRef.current?.querySelector<HTMLElement>('.map-gesture-hint');
    const grid=contentRef.current?.querySelector<HTMLElement>('.dashboard-grid');
    if(!panel||!hint)return;
    let frame: number|null=null;
    const update=()=>{
      const dockTop=hint.getBoundingClientRect().top-8;
      const mapBounds=panel.getBoundingClientRect();
      setMapControlsVisible(mapBounds.top<dockTop&&mapBounds.bottom>dockTop&&(!comparison||comparison.getBoundingClientRect().top>dockTop));
      const firstInfoPanel=grid?.querySelector<HTMLElement>('.dashboard-left .card, .dashboard-right .card');
      setMobilePanelHintVisible(Boolean(firstInfoPanel && firstInfoPanel.getBoundingClientRect().top>=innerHeight));
    };
    const schedule=()=>{if(frame===null)frame=requestAnimationFrame(()=>{frame=null;update();});};
    const observer=new ResizeObserver(schedule);
    observer.observe(panel);
    if(grid)observer.observe(grid);
    window.addEventListener('scroll',schedule,{passive:true});
    window.addEventListener('resize',schedule);
    update();
    return()=>{
      if(frame!==null)cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener('scroll',schedule);
      window.removeEventListener('resize',schedule);
    };
  },[tab,advancedPanels,hasSelectedMunicipality]);
  const helpReturnTab=useRef('inicio');
  const helpReturnScroll=useRef(0);
  const previousScreen=useRef(tab);
  useLayoutEffect(()=>{
    if(previousScreen.current===tab)return;
    const previous=previousScreen.current;
    previousScreen.current=tab;
    if(tab==='ajuda')window.scrollTo(0,0);
    else if(previous==='ajuda' && tab===helpReturnTab.current)window.scrollTo(0,helpReturnScroll.current);
    if(window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;
    const animation=contentRef.current?.animate([{opacity:0},{opacity:1}],{duration:260,easing:'ease-out'});
    return()=>animation?.cancel();
  },[tab]);
  useEffect(()=>{if(!hasSelectedMunicipality)setAdvancedPanels(false);},[hasSelectedMunicipality]);
  const latestWeek = indicators?.serie.slice().reverse().find(point => point.casos !== null);
  const [refreshIndicators,setRefreshIndicators] = useState(0);
  const [mapOptions,setMapOptions] = useState<IndicatorOptions|null>(null);
  const availableCityCodes=useMemo(()=>new Set(mapOptions?.integracoes.flatMap(item=>item.codigos_com_dados||[])||[]),[mapOptions]);
  const mapSignals=useMemo(()=>{
    const strongest=new Map<string,MapSignal>();
    const selectedIndicator=indicators?.integracao?.codigo;
    for(const signal of mapOptions?.sinalizacoes_mapa||[]){
      if(selectedIndicator&&signal.indicador!==selectedIndicator)continue;
      const previous=strongest.get(signal.codigo);
      if(!previous || signal.observado/signal.limiar > previous.observado/previous.limiar)
        strongest.set(signal.codigo,signal);
    }
    return strongest;
  },[mapOptions,indicators?.integracao?.codigo]);
  const mapLatestWeeks=useMemo(()=>new Map(
    (mapOptions?.ultimas_semanas_mapa||[]).map(week=>[`${week.codigo}:${week.indicador}`,week])
  ),[mapOptions]);
  const [mapSelection,setMapSelection] = useState<MapSelection|null>(null);
  const mapSelectionSequence=useRef(0);
  const [filterResetSequence,setFilterResetSequence]=useState(0);
  const [pickedCity,setPickedCity] = useState<PickedCity|null>(null);
  useEffect(()=>{if(tab!=='inicio'){setMapSelection(null);setPickedCity(null);}},[tab]);
  const territory = useRef<Indicators['territorio']|null>(null);
  territory.current = indicators?.territorio ?? null;
  const selectedCodes = useMemo(()=>new Set(indicators?.territorio.tipo === 'regiao'
    ? (immediateRegions as Record<string,string[]>)[indicators.territorio.codigo] || []
    : indicators ? [indicators.territorio.codigo] : []),[indicators]);
  const [municipalities, setMunicipalities] = useState<Municipality[]>([]);
  const selectedMapCity = useMemo(() => indicators?.territorio.tipo === 'municipio'
    ? municipalities.find(city => city.id === indicators.territorio.codigo)
    : undefined, [indicators?.territorio.tipo, indicators?.territorio.codigo, municipalities]);
  useEffect(() => {
    if (tab !== 'inicio') return;
    let active = true;
    import('./municipalities.json').then(data => { if (active) setMunicipalities(data.default); }).catch(() => { if (active) setError('Não foi possível carregar os limites municipais. Atualize a página para tentar novamente.'); });
    return () => { active = false; };
  }, [tab]);
  const tourCities=useMemo(()=>municipalities.filter(city=>availableCityCodes.has(city.id)),[municipalities,availableCityCodes]);
  const [tourCity,setTourCity]=useState<Municipality|null>(null);
  const tourIntegrations=useMemo(()=>tourCity?availableCityIntegrations(mapOptions,tourCity.id):[],[mapOptions,tourCity]);
  const tourPrimaryIntegration=tourIntegrations[0];
  const tourPreviewEngaged=useRef(false);
  const [tourPaused,setTourPaused]=useState(false);
  const [tourRestart,setTourRestart]=useState(0);
  const tourCityCode=useRef<string|null>(null);
  const lastTourCityCode=useRef<string|null>(null);
  const tourAllowed=useRef(false);
  tourAllowed.current=tab==='inicio'&&!hasSelectedMunicipality&&!tourPaused;
  const [page, setPage] = useState<SourcePage>({ sources: [], arquivadas: false, count: 0, page: 1, pages: 1, coleta_realizada: false });
  const [sourceSearch,setSourceSearch]=useState('');
  const sourceSearchRef=useRef(sourceSearch);sourceSearchRef.current=sourceSearch;
  const [showArchived,setShowArchived]=useState(false);
  const showArchivedRef=useRef(showArchived);showArchivedRef.current=showArchived;
  const sourceRequest=useRef(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useTimedMessage();
  const [success, setSuccess] = useTimedMessage(5000);
  const [editor, setEditor] = useState<Source | 'new' | null>(null);
  const [mapView, setMapView] = useState({ zoom: 0.8, pan: { x: 0, y: 0 } });
  const currentMapView = useRef(mapView);
  const [activeMapRegion,setActiveMapRegion]=useState<number|null>(null);
  const activeMapRegionRef=useRef<number|null>(null);
  const [mapPixelScale,setMapPixelScale]=useState(1);
  const mapPixelScaleRef=useRef(mapPixelScale);mapPixelScaleRef.current=mapPixelScale;
  const mapGroup = useRef<SVGGElement>(null);
  const mapAnimation = useRef<number|null>(null);
  const reducedMapAnimation = useRef(false);
  function cancelMapAnimation() {
    if(mapAnimation.current!==null){cancelAnimationFrame(mapAnimation.current);setMapView(currentMapView.current);}
    mapAnimation.current=null;
  }
  function moveMap(target: typeof mapView, animated=true, duration=700) {
    cancelMapAnimation();
    // Anima apenas o grupo SVG; não reconstrói os 645 municípios em cada quadro.
    const regionLabels=mapGroup.current?.querySelectorAll<SVGGElement>('.map-region-labels > g');
    const write=(view:typeof mapView,commit=true)=>{
      currentMapView.current=view;
      mapGroup.current?.setAttribute('transform',`translate(${view.pan.x} ${view.pan.y}) translate(360 220) scale(${view.zoom}) translate(-360 -220)`);
      // Mantém os nomes das regiões legíveis durante o zoom animado.
      const labelScale=Math.max(.01,mapPixelScaleRef.current*view.zoom);
      regionLabels?.forEach(label=>{
        const {regionX,regionY,offsetX,offsetY}=label.dataset;
        if(regionX===undefined||regionY===undefined)return;
        label.setAttribute('transform',`translate(${Number(regionX)+Number(offsetX||0)/labelScale} ${Number(regionY)+Number(offsetY||0)/labelScale}) scale(${1/labelScale})`);
      });
      if(commit)setMapView(view);
    };
    if(!animated || window.matchMedia('(prefers-reduced-motion: reduce)').matches || (innerWidth<=760&&reducedMapAnimation.current)){write(target);return;}
    const start=currentMapView.current, started=performance.now();
    let lastFrame=0, frames=0, slowFrames=0;
    const frame=(now:number)=>{
      if(innerWidth<=760 && !document.hidden && lastFrame){
        frames++;
        if(now-lastFrame>42)slowFrames++;
        // Quadros repetidamente acima de 42 ms indicam que este aparelho não acompanha o SVG.
        if(frames>=12 && slowFrames>=5){
          reducedMapAnimation.current=true;
          mapAnimation.current=null;
          write(target);
          return;
        }
      }
      lastFrame=now;
      const progress=Math.min(1,(now-started)/duration);
      const ease=progress<.5 ? 4*progress**3 : 1-(-2*progress+2)**3/2;
      write({zoom:start.zoom*(target.zoom/start.zoom)**ease,pan:{x:start.pan.x+(target.pan.x-start.pan.x)*ease,y:start.pan.y+(target.pan.y-start.pan.y)*ease}},false);
      if(progress<1) mapAnimation.current=requestAnimationFrame(frame);
      else {mapAnimation.current=null;write(target);}
    };
    mapAnimation.current=requestAnimationFrame(frame);
  }
  const { zoom } = mapView;
  const mapRef = useRef<SVGSVGElement>(null);
  const mapRegions=useMemo(()=>buildMapRegions(municipalities),[municipalities]);
  useLayoutEffect(()=>{
    const svg=mapRef.current;
    if(tab!=='inicio'||!svg||!municipalities.length)return;
    const bounds=svg.getBoundingClientRect();
    const scale=Math.min(bounds.width/780,bounds.height/500);
    mapPixelScaleRef.current=scale;
    setMapPixelScale(scale);
  },[tab,municipalities]);
  const labelScale=mapPixelScale*zoom;
  const zoomAnchor = useRef({x:360,y:220});
  const fitMode = useRef<'estado'|'recorte'|'regiao'|'passeio'>('estado');
  const lastTerritory = useRef<string|null>(null);
  function pauseMapTour() {
    if(!tourAllowed.current)return;
    tourAllowed.current=false;
    tourPreviewEngaged.current=false;
    tourCityCode.current=null;
    setTourCity(null);
    setTourPaused(true);
    fitMode.current='estado';
    cancelMapAnimation();
  }
  function fitMap(mode: 'estado'|'recorte'|'regiao'|'passeio', animated=true) {
    const svg = mapRef.current;
    const matrix = svg?.getScreenCTM();
    if (!svg || !matrix) return;
    const current = territory.current;
    const codes = new Set(mode === 'passeio' && tourCityCode.current ? [tourCityCode.current]
      : mode === 'recorte' && current ? current.tipo === 'regiao'
        ? (immediateRegions as Record<string,string[]>)[current.codigo] || [] : [current.codigo] : []);
    const shapes = mode === 'regiao' && activeMapRegionRef.current !== null
      ? Array.from(svg.querySelectorAll<SVGPathElement>(`[data-intermediate-region="${activeMapRegionRef.current}"]`))
      : (mode === 'recorte' || mode === 'passeio') && codes.size
        ? Array.from(svg.querySelectorAll<SVGPathElement>('[data-municipality]')).filter(p=>codes.has(p.dataset.municipality!))
        : [svg.querySelector<SVGPathElement>('[data-state]')!];
    const bounds = shapes.filter(Boolean).map(p=>p.getBBox());
    if (!bounds.length) return;
    const left = Math.min(...bounds.map(b=>b.x)), top = Math.min(...bounds.map(b=>b.y));
    const right = Math.max(...bounds.map(b=>b.x+b.width)), bottom = Math.max(...bounds.map(b=>b.y+b.height));
    const panel = svg.closest('.territory-panel')!.getBoundingClientRect();
    let area = {left: panel.left+24, right: panel.right-24, top: Math.max(24,panel.top+48), bottom: Math.min(innerHeight-24,panel.bottom-64)};
    if (area.bottom-area.top<140 || area.right-area.left<140) area = {left:24,right:innerWidth-24,top:120,bottom:innerHeight-80};
    const inverse=matrix.inverse();
    const a=new DOMPoint(area.left,area.top).matrixTransform(inverse), b=new DOMPoint(area.right,area.bottom).matrixTransform(inverse);
    // Margem mantém os municípios vizinhos visíveis; o estado inteiro cabe mesmo em telas estreitas.
    const fill=mode==='regiao' ? (innerWidth<=760?.86:.72) : mode==='passeio' ? .68 : (innerWidth<=760?.94:.8);
    const next=Math.min(mode==='passeio'?5.5:10, Math.max(.1, Math.min((b.x-a.x)/Math.max(1,right-left),(b.y-a.y)/Math.max(1,bottom-top))*fill));
    zoomAnchor.current={x:(a.x+b.x)/2,y:(a.y+b.y)/2};
    drag.current=null; setHoveredCity(null);
    moveMap({zoom:next,pan:{x:(a.x+b.x)/2-360-next*((left+right)/2-360),y:(a.y+b.y)/2-220-next*((top+bottom)/2-220)}},animated,mode==='passeio'?1300:700);
  }
  function focusMapRegion(index:number) {
    if(index<0 || index>=intermediateRegions.length)return;
    pauseMapTour();
    activeMapRegionRef.current=index;
    setActiveMapRegion(index);
    fitMode.current='regiao';
    setPickedCity(null);
    setHoveredCity(null);
    fitMap('regiao');
  }
  function resetMapRegions() {
    pauseMapTour();
    activeMapRegionRef.current=null;
    setActiveMapRegion(null);
    fitMode.current='estado';
    setPickedCity(null);
    setHoveredCity(null);
    fitMap('estado');
    if(!hasSelectedMunicipality)setTourPaused(false);
  }
  function restoreMapAndTour() {
    resetMapRegions();
    lastTerritory.current=null;
    tourCityCode.current=null;
    setTourCity(null);
    setMapSelection(null);
    setIndicators(null);
    setFilterResetSequence(value=>value+1);
    setTourPaused(false);
    setTourRestart(value=>value+1);
  }
  useEffect(()=>{
    if(tab !== 'inicio' || !municipalities.length || !indicators) return;
    const key=`${indicators.territorio.tipo}:${indicators.territorio.codigo}`;
    if(lastTerritory.current===key) return;
    lastTerritory.current=key;
    const region=indicators.territorio.tipo==='municipio'
      ? getIntermediateRegionIndex(indicators.territorio.codigo)
      : getIntermediateRegionIndex((immediateRegions as Record<string,string[]>)[indicators.territorio.codigo]?.[0]||'');
    activeMapRegionRef.current=region>=0?region:null;
    setActiveMapRegion(activeMapRegionRef.current);
    fitMode.current='recorte';
    if(innerWidth<=760) mapRef.current?.closest('.territory-panel')?.scrollIntoView({block:'end'});
    const frame=requestAnimationFrame(()=>fitMap(fitMode.current));
    return()=>cancelAnimationFrame(frame);
  },[indicators?.territorio.tipo,indicators?.territorio.codigo,municipalities,tab]);
  useEffect(()=>{
    if(tab!=='inicio'||hasSelectedMunicipality||tourPaused||!tourCities.length||window.matchMedia('(prefers-reduced-motion: reduce)').matches){
      tourCityCode.current=null;
      setTourCity(null);
      return;
    }
    let timer=0;
    let queue:Municipality[]=[];
    const next=()=>{
      if(document.hidden||tourPreviewEngaged.current){timer=window.setTimeout(next,1000);return;}
      if(!queue.length){
        queue=[...tourCities];
        for(let index=queue.length-1;index>0;index--){
          const random=Math.floor(Math.random()*(index+1));
          [queue[index],queue[random]]=[queue[random],queue[index]];
        }
        if(queue.length>1&&queue[0].id===lastTourCityCode.current)[queue[0],queue[1]]=[queue[1],queue[0]];
      }
      const city=queue.shift()!;
      lastTourCityCode.current=city.id;
      tourCityCode.current=city.id;
      setTourCity(city);
      fitMode.current='passeio';
      fitMap('passeio');
      timer=window.setTimeout(next,6500);
    };
    timer=window.setTimeout(next,700);
    return()=>{window.clearTimeout(timer);tourPreviewEngaged.current=false;};
  },[tab,hasSelectedMunicipality,tourPaused,tourCities,tourRestart]);
  useEffect(()=>{
    if(tab!=='inicio') return;
    let frame=0;
    let layout='';
    // Alterações de layout (inclusive a barra de rolagem) não devem interromper uma viagem em curso.
    const resize=()=>{
      cancelAnimationFrame(frame);
      frame=requestAnimationFrame(()=>{
        const svg=mapRef.current;
        const panel=svg?.closest('.territory-panel');
        if(!svg || !panel) return;
        // A barra de endereço móvel dispara resize durante a rolagem. Só reenquadrar
        // quando o tamanho do mapa/painel mudar, nunca por sua posição na página.
        const mapBounds=svg.getBoundingClientRect(), panelBounds=panel.getBoundingClientRect();
        const next=[mapBounds.width,mapBounds.height,panelBounds.width,panelBounds.height].map(Math.round).join(':');
        if(next===layout) return;
        layout=next;
        const scale=Math.min(mapBounds.width/780,mapBounds.height/500);
        mapPixelScaleRef.current=scale;
        setMapPixelScale(scale);
        fitMap(fitMode.current,mapAnimation.current!==null);
      });
    };
    const observer=new ResizeObserver(resize);
    if(mapRef.current){observer.observe(mapRef.current);observer.observe(mapRef.current.closest('.territory-panel')!);}
    window.addEventListener('resize',resize);resize();
    return()=>{observer.disconnect();window.removeEventListener('resize',resize);cancelAnimationFrame(frame);cancelMapAnimation();};
  },[tab,municipalities]);
  const [hoveredCity, setHoveredCity] = useState<{ id: string; name: string; x: number; y: number } | null>(null);
  const hoveredMapRegion=activeMapRegion===null&&hoveredCity?getIntermediateRegionIndex(hoveredCity.id):null;
  const suppressMapClick=useRef(false);
  function selectMapIntegration(cityCode:string, integration:Integration) {
    setMapSelection({cityCode,integrationCode:integration.codigo,requestId:++mapSelectionSequence.current});
    setPickedCity(null);
  }
  function openCity(city:Municipality, x:number, y:number) {
    pauseMapTour();
    setHoveredCity(null);
    const integrations=availableCityIntegrations(mapOptions,city.id);
    if(integrations.length===1){selectMapIntegration(city.id,integrations[0]);return;}
    setPickedCity({id:city.id,name:city.name,x,y});
  }
  function selectMapCity(city:Municipality, x:number, y:number) {
    const region=getIntermediateRegionIndex(city.id);
    if(region<0)return;
    if(activeMapRegionRef.current!==region){focusMapRegion(region);return;}
    openCity(city,x,y);
  }
  function mapTooltipMessage(city:{id:string}) {
    const signal=mapSignals.get(city.id);
    const signalSource=mapOptions?.integracoes.find(item=>item.codigo===signal?.indicador);
    const signalText=signal ? ` ${signalSource?.agravo_nome||'Série monitorada'}: sinalização ${['','leve','moderada','forte'][signal.nivel]} na semana de ${signal.data_referencia.split('-').reverse().join('/')}: ${signal.observado.toLocaleString('pt-BR')} casos, acima do limiar de ${exactDecimal(signal.limiar)}. Não confirma surto.` : '';
    if(activeMapRegion===null || activeMapRegion!==getIntermediateRegionIndex(city.id)){
      const region=intermediateRegions[getIntermediateRegionIndex(city.id)];
      return (region ? `Clique para ampliar a região de ${region.name}.` : 'Escolha uma região no mapa.')+signalText;
    }
    return (availableCityCodes.has(city.id) ? 'Clique para consultar os dados disponíveis.' : 'Sem dados processados para este município.')+signalText;
  }
  function mapCityActionLabel(city:Municipality) {
    const region=getIntermediateRegionIndex(city.id);
    return activeMapRegion===region ? `Consultar dados de ${city.name}` : `Ampliar região de ${intermediateRegions[region]?.name||city.name}`;
  }
  function changeZoom(factor: number, anchor = zoomAnchor.current, animated=true) {
      const view=currentMapView.current;
      const next = Math.max(.1, Math.min(10, view.zoom * factor));
      const ratio = next / view.zoom;
      moveMap({ zoom: next, pan: { x: anchor.x - 360 - (anchor.x - 360 - view.pan.x) * ratio, y: anchor.y - 220 - (anchor.y - 220 - view.pan.y) * ratio } },animated,220);
  }
  useEffect(() => {
    const svg = mapRef.current;
    if (!svg || tab !== 'inicio') return;
    const wheel = (event: WheelEvent) => {
      if (!event.ctrlKey) return;
      pauseMapTour();
      event.preventDefault();
      const matrix = svg.getScreenCTM();
      if (!matrix) return;
      const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? window.innerHeight : 1);
      changeZoom(Math.exp(-Math.max(-160, Math.min(160, delta)) * .002), point,false);
    };
    let pinch: { distance: number; center: DOMPoint; view: typeof mapView } | null = null;
    const gesture = (event: TouchEvent) => {
      if (event.touches.length !== 2) return null;
      const matrix = svg.getScreenCTM();
      if (!matrix) return null;
      const [a, b] = Array.from(event.touches);
      return { distance: Math.hypot(a.clientX-b.clientX, a.clientY-b.clientY), center: new DOMPoint((a.clientX+b.clientX)/2, (a.clientY+b.clientY)/2).matrixTransform(matrix.inverse()) };
    };
    const touchStart = (event: TouchEvent) => {
      const pair = gesture(event);
      if (!pair || pair.distance === 0) return;
      pauseMapTour();
      event.preventDefault(); cancelMapAnimation(); drag.current = null; setHoveredCity(null);
      pinch = { ...pair, view: currentMapView.current };
    };
    const touchMove = (event: TouchEvent) => {
      const pair = gesture(event);
      if (!pair || !pinch) return;
      event.preventDefault();
      const next = Math.max(.1, Math.min(10, pinch.view.zoom * pair.distance / pinch.distance));
      const ratio = next / pinch.view.zoom;
      moveMap({zoom:next, pan:{x:pair.center.x-360-(pinch.center.x-360-pinch.view.pan.x)*ratio, y:pair.center.y-220-(pinch.center.y-220-pinch.view.pan.y)*ratio}},false);
    };
    const touchEnd = () => { pinch = null; };
    svg.addEventListener('wheel', wheel, { passive: false });
    svg.addEventListener('touchstart', touchStart, { passive: false });
    svg.addEventListener('touchmove', touchMove, { passive: false });
    svg.addEventListener('touchend', touchEnd);
    svg.addEventListener('touchcancel', touchEnd);
    return () => {
      svg.removeEventListener('wheel', wheel);
      svg.removeEventListener('touchstart', touchStart);
      svg.removeEventListener('touchmove', touchMove);
      svg.removeEventListener('touchend', touchEnd);
      svg.removeEventListener('touchcancel', touchEnd);
    };
  }, [tab]);
  useEffect(()=>{
    if(tab!=='inicio')return;
    const svg=mapRef.current;
    const dock=svg?.closest('.territory-panel')?.querySelector('.map-controls-dock');
    const dashboardTools=svg?.closest('.monitoring-shell')?.querySelector('.dashboard-tools');
    const pause=(event:Event)=>{
      if(event.target instanceof Element && event.target.closest('.advanced-panels-toggle'))return;
      pauseMapTour();
    };
    const pauseOnKey=(event:Event)=>{if((event as KeyboardEvent).key==='Enter'||(event as KeyboardEvent).key===' ')pause(event);};
    svg?.addEventListener('pointerdown',pause,true);
    svg?.addEventListener('keydown',pauseOnKey,true);
    dock?.addEventListener('pointerdown',pause,true);
    dock?.addEventListener('keydown',pauseOnKey,true);
    dashboardTools?.addEventListener('pointerdown',pause,true);
    dashboardTools?.addEventListener('keydown',pauseOnKey,true);
    return()=>{
      svg?.removeEventListener('pointerdown',pause,true);
      svg?.removeEventListener('keydown',pauseOnKey,true);
      dock?.removeEventListener('pointerdown',pause,true);
      dock?.removeEventListener('keydown',pauseOnKey,true);
      dashboardTools?.removeEventListener('pointerdown',pause,true);
      dashboardTools?.removeEventListener('keydown',pauseOnKey,true);
    };
  },[tab]);
  const drag = useRef<{ x: number; y: number; panX: number; panY: number; moved:boolean } | null>(null);
  const [collecting, setCollecting] = useState<number | null>(null);
  const [archiving, setArchiving] = useState<number | null>(null);
  const [collectionHistory, setCollectionHistory] = useState<{ source: Source; runs: CollectionRun[] } | null>(null);
  async function archiveSource(source: Source, archive: boolean) {
    if (archive && !window.confirm(`Arquivar ${territoryLabel(source)}? A coleta será interrompida e o histórico permanecerá disponível.`)) return;
    const originTab=currentTab.current;
    setArchiving(source.id);setError('');setSuccess('');
    try {
      await api(`/fontes/${source.id}/arquivamento/`, 'PUT', {arquivar: archive});
      if(currentTab.current===originTab)setSuccess(archive?'Fonte arquivada. O histórico foi preservado.':'Fonte restaurada e desabilitada. Edite-a para reativar a coleta.');
      setCollectionHistory(null);
      await load(page.page,false);
    } catch (err) { if(err instanceof ApiError&&err.status===401)onLogout();else if(currentTab.current===originTab)setError(describe(err)); }
    finally {setArchiving(null);}
  }
  async function collect(source: Source) {
    const originTab=currentTab.current;
    setCollecting(source.id); setError(''); setSuccess('');
    try {
      const data = await api<{ execucao: CollectionRun }>(`/fontes/${source.id}/coletas/`, 'POST', {});
      if(currentTab.current===originTab)setSuccess(data.execucao.status === 'vazia' ? `${source.nome}: ${data.execucao.mensagem}` : `${source.nome}: ${data.execucao.quantidade_registros} registros brutos coletados.${data.execucao.repetida ? ' Conteúdo já armazenado; sem duplicação.' : ''} Consulte a situação do processamento na lista.`);
    } catch (err) { if (err instanceof ApiError && err.status === 401) onLogout(); else if(currentTab.current===originTab)setError(describe(err)); }
    finally { setCollecting(null); setRefreshIndicators(v=>v+1); void load(page.page, false); }
  }
  async function showHistory(source: Source) {
    try { const data = await api<{ execucoes: CollectionRun[] }>(`/fontes/${source.id}/coletas/`); setCollectionHistory({ source, runs: data.execucoes }); }
    catch (err) { if (err instanceof ApiError && err.status === 401) onLogout(); else setError(describe(err)); }
  }
  async function load(number = 1, clearError = true, silent = false) {
    const version=++sourceRequest.current;
    if(!silent)setLoading(true); if (clearError) setError('');
    const params=new URLSearchParams({page:String(number)});
    if(currentTab.current==='fontes' && sourceSearchRef.current.trim())params.set('q',sourceSearchRef.current.trim());
    if(currentTab.current==='fontes' && showArchivedRef.current)params.set('arquivadas','1');
    try { const result=await api<SourcePage>(`/fontes/?${params}`);if(version===sourceRequest.current)setPage(result); }
    catch (err) { if(version===sourceRequest.current){if (err instanceof ApiError && err.status === 401) onLogout(); else setError(describe(err));} }
    finally { if(version===sourceRequest.current&&!silent)setLoading(false); }
  }
  useEffect(() => {
    ++sourceRequest.current;setLoading(true);
    const timer=setTimeout(()=>void load(),tab==='fontes'?250:0);
    return()=>{clearTimeout(timer);++sourceRequest.current;};
  }, [tab,sourceSearch,showArchived]);
  const initialCollectionPending=page.sources.some(source=>source.coleta_inicial_status==='pendente'||source.coleta_inicial_status==='executando');
  useEffect(()=>{
    if(tab!=='fontes'||page.arquivadas||!initialCollectionPending)return;
    const timer=window.setInterval(()=>void load(page.page,false,true),5000);
    return()=>window.clearInterval(timer);
  },[tab,page.arquivadas,page.page,initialCollectionPending]);
  const [processingNotice,setProcessingNotice]=useTimedMessage();
  useEffect(()=>{const count=page.falhas_processamento||0;setProcessingNotice(count?`${count} ${count===1?'fonte com falha':'fontes com falha'} de processamento. Os dados brutos foram preservados.`:'');},[page.falhas_processamento,setProcessingNotice]);
  useEffect(()=>{setSuccess('');setError('');setProcessingNotice('');},[tab,setSuccess,setError,setProcessingNotice]);
  async function signOut() {
    try { await api('/auth/logout/', 'POST'); onLogout(); }
    catch (err) { if (err instanceof ApiError && err.status === 401) onLogout(); else setError(describe(err)); }
  }
  return <div className={`app-shell ${tab === 'inicio' ? `monitoring-shell${hasSelectedMunicipality?'':' monitoring-awaiting-selection'}` : tab === 'fontes' ? 'sources-shell' : tab === 'administracao' ? 'administration-shell' : ''}`}>

    <header className="topbar"><Brand onClick={()=>{setTab('inicio');setEditor(null);window.scrollTo(0,0);}}/><nav className="main-navigation" data-screen={tab} aria-label="Navegação principal"><span className="navigation-indicator" aria-hidden="true"/><button aria-current={tab === 'inicio' ? 'page' : undefined} className={tab === 'inicio' ? 'selected' : ''} onClick={() => { setTab('inicio'); setEditor(null); }} data-icon="activity"><ActionIcon name="activity"/>Monitoramento</button>{<button aria-current={tab === 'fontes' ? 'page' : undefined} className={tab === 'fontes' ? 'selected' : ''} onClick={() => { setTab('fontes'); setSuccess(''); }} data-icon="database"><ActionIcon name="database"/>Fontes de dados</button>}</nav><div className="header-actions"><button className="secondary help-nav-button" aria-label={tab==='ajuda'?'Fechar ajuda e voltar à tela anterior':'Ajuda'} title={tab==='ajuda'?'Voltar à tela anterior':'Ajuda'} aria-current={tab==='ajuda'?'page':undefined} onClick={()=>{if(tab==='ajuda'){setTab(helpReturnTab.current);}else{helpReturnTab.current=tab;helpReturnScroll.current=window.scrollY;setTab('ajuda');}}} data-icon={tab==='ajuda'?'close':'help'}><ActionIcon name={tab==='ajuda'?'close':'help'}/></button><AlertCenter onExpired={onLogout}/><AccountMenu user={user} onAdministration={user.administrador?()=>{setTab("administracao");setEditor(null);}:undefined} onLogout={()=>void signOut()}/></div></header>
    <main className="content" ref={contentRef}>
      {tab === 'fontes' && collectionHistory && <section className="card collection-history" aria-label="Histórico de coleta"><div className="section-heading"><div><h2>Coletas · {territoryLabel(collectionHistory.source)}</h2><small>{sourcePeriodLabel(collectionHistory.source)}</small></div><button className="secondary" onClick={() => setCollectionHistory(null)} data-icon="close"><ActionIcon name="close"/>Fechar histórico</button></div>{collectionHistory.runs.length === 0 ? <p>Nenhuma coleta executada.</p> : <ul>{collectionHistory.runs.map(run => <li key={run.id}><strong>{run.status === 'sucesso' ? 'Concluída' : run.status === 'vazia' ? 'Sem registros' : run.status === 'erro' ? 'Falha' : 'Executando'} · {new Date(run.iniciada_em).toLocaleString('pt-BR')}</strong><p>{run.mensagem}</p><small>{run.quantidade_registros} registros · {run.origem === 'airflow' ? 'Agendada' : run.origem === 'inicial' ? 'Primeira coleta automática' : 'Manual'}{run.repetida ? ' · Conteúdo já armazenado' : ''}</small></li>)}</ul>}</section>}

      <Notice message={canSources?processingNotice:''}><button className="secondary" onClick={()=>setTab('fontes')} data-icon="database"><ActionIcon name="database"/>Consultar fontes</button></Notice>
      <Notice message={error}><button className="secondary" onClick={() => void load(page.page)} data-icon="refresh"><ActionIcon name="refresh"/>Tentar novamente</button></Notice>
      <Notice message={success} kind="success"/>
      {tab === 'inicio' ? <>
      <div className="dashboard-layout">
      <div className="dashboard-heading"><div className="dashboard-title"><span className="eyebrow">PAINEL TERRITORIAL</span><h1>Monitoramento epidemiológico</h1></div><div className="dashboard-tools"><button type="button" className="secondary filter-trigger advanced-panels-toggle" disabled={!hasSelectedMunicipality} aria-expanded={showDetailedPanels} aria-controls="dashboard-left dashboard-right" onClick={()=>setAdvancedPanels(value=>!value)} data-icon={showDetailedPanels?'close':'list'}><ActionIcon name={showDetailedPanels?'close':'list'}/>{showDetailedPanels?'Mostrar resumo':'Informações detalhadas'}</button><ExportDataGate user={user} data={indicators} onExpired={onLogout}/><IndicatorFilters onData={setIndicators} onOptions={setMapOptions} onExpired={onLogout} refresh={refreshIndicators} mapSelection={mapSelection} resetSelection={filterResetSequence} appliedData={indicators}/></div></div>
      {!hasSelectedMunicipality && <p className="map-selection-hint" role="status"><strong>Para ver os dados:</strong> {tourCity ? 'selecione o resumo do município em destaque ou escolha um município no mapa.' : activeMapRegion === null ? 'selecione uma região e depois um município no mapa.' : 'selecione um município destacado no mapa.'}</p>}
      <p className="mobile-panel-hint" hidden={!hasSelectedMunicipality||!mobilePanelHintVisible}>Role para ver os painéis de informações ↓</p>
      <div className="dashboard-grid">
        <aside id="dashboard-left" className={`dashboard-left ${advancedPanels?'advanced':'compact'}`}>{hasSelectedMunicipality && (advancedPanels ? <>
          {indicators&&<DataQuality data={indicators}/>}<SeriesChart data={indicators}/>
          </> : <><CompactOverview data={indicators}/><CompactRecent data={indicators} latestWeek={latestWeek}/><CompactQuality data={indicators}/></>)}
        </aside>
        <section className="territory-panel" aria-label="Mapa de referência do estado de São Paulo"><div className={`map-stage${mapControlsVisible ? "" : " map-controls-hidden"}`}><svg ref={mapRef} className="interactive-map" viewBox="-30 -30 780 500" role="group" aria-labelledby="map-title map-description" onPointerDown={e => { if (e.pointerType === 'touch' || e.button !== 0) return; suppressMapClick.current=false; cancelMapAnimation(); setHoveredCity(null); setPickedCity(null); const path=(e.target as Element).closest('[data-municipality], [data-map-region]'); if(!path)e.currentTarget.setPointerCapture(e.pointerId); drag.current = { x: e.clientX, y: e.clientY, panX: currentMapView.current.pan.x, panY: currentMapView.current.pan.y, moved:false }; }} onPointerMove={e => { if (!drag.current) return; if(Math.hypot(e.clientX-drag.current.x,e.clientY-drag.current.y)>5){drag.current.moved=true;if(!e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.setPointerCapture(e.pointerId);} if(!drag.current.moved)return; const matrix = e.currentTarget.getScreenCTM(); if (!matrix) return; const inverse = matrix.inverse(); const start = new DOMPoint(drag.current.x, drag.current.y).matrixTransform(inverse); const current = new DOMPoint(e.clientX, e.clientY).matrixTransform(inverse); const nextPan = { x: drag.current.panX + current.x - start.x, y: drag.current.panY + current.y - start.y }; moveMap({ ...currentMapView.current, pan: nextPan },false); }} onPointerUp={() => { suppressMapClick.current=Boolean(drag.current?.moved); drag.current=null; }} onPointerCancel={() => { drag.current = null; }} onLostPointerCapture={() => { drag.current = null; }}><title id="map-title">Contorno do estado de São Paulo</title><desc id="map-description">Mapa em duas etapas: escolha uma região geográfica intermediária de São Paulo para aproximar e depois selecione um município. Passe o mouse sobre um município para ver seu nome. Vermelho indica casos acima do limiar estatístico em alguma das quatro semanas mais recentes da base; a tonalidade indica a intensidade do excesso, não confirma surto.</desc><defs><linearGradient id="map-fill" x2="1" y2="1"><stop stopColor="#293b5c"/><stop offset="1" stopColor="#142238"/></linearGradient></defs><g ref={mapGroup} transform={`translate(${currentMapView.current.pan.x} ${currentMapView.current.pan.y}) translate(360 220) scale(${currentMapView.current.zoom}) translate(-360 -220)`}><path data-state d={saoPauloPath} fill="url(#map-fill)" stroke="#668ad0" strokeWidth="1.5"/>{municipalities.map(city => <path key={city.id} data-municipality={city.id} data-intermediate-region={getIntermediateRegionIndex(city.id)} d={city.path} tabIndex={activeMapRegion!==null&&availableCityCodes.has(city.id)?0:undefined} role={activeMapRegion!==null&&availableCityCodes.has(city.id)?'button':undefined} aria-label={activeMapRegion!==null&&availableCityCodes.has(city.id)?mapCityActionLabel(city):undefined} onKeyDown={event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();const bounds=event.currentTarget.getBoundingClientRect();selectMapCity(city,bounds.left+bounds.width/2,bounds.top+bounds.height/2);}}} className={`municipality ${hoveredMapRegion===getIntermediateRegionIndex(city.id)?'region-hovered':''} ${activeMapRegion===getIntermediateRegionIndex(city.id)?'region-selected':''} ${selectedCodes.has(city.id) ? 'selected-territory' : ''} ${selectedMapCity?.id===city.id ? 'selected-municipality' : ''} ${hoveredCity?.id === city.id || pickedCity?.id === city.id ? 'highlighted' : ''} ${availableCityCodes.has(city.id) ? 'has-data' : ''} ${mapSignals.has(city.id) ? `signal-${mapSignals.get(city.id)?.nivel}` : ''} ${tourCity?.id===city.id ? 'touring' : ''}`} fill="transparent" stroke="#4a6286" strokeWidth=".65" onPointerMove={event => { if (event.pointerType === 'touch' || drag.current) return; setHoveredCity({ id: city.id, name: city.name, x: Math.max(12, Math.min(window.innerWidth - 272, event.clientX + 16)), y: Math.max(12, Math.min(window.innerHeight - 140, event.clientY + 16)) }); }} onPointerLeave={() => setHoveredCity(null)} onClick={event=>{if(suppressMapClick.current){suppressMapClick.current=false;return;}selectMapCity(city,event.clientX,event.clientY);}}><title>{city.name} · IBGE {city.id}{mapSignals.has(city.id) ? ' · casos acima do limiar esperado' : ''}</title></path>)}<path className="map-region-borders" d={mapRegions.borders}/>{activeMapRegion!==null&&<path className="map-selected-region-outline" d={mapRegions.outlines[activeMapRegion]} aria-hidden="true"/>}{selectedMapCity&&<path className="map-selected-outline" d={selectedMapCity.path} aria-hidden="true"/>}<MapRegionLabels labels={mapRegions.labels} pixelsPerUnit={labelScale} focusedCode={activeMapRegion===null?null:intermediateRegions[activeMapRegion].code} onSelect={code=>focusMapRegion(intermediateRegions.findIndex(region=>region.code===code))}/></g></svg>{tourCity&&tourPrimaryIntegration&&!hasSelectedMunicipality&&<MapTourPreview cityName={tourCity.name} integrations={tourIntegrations} latestWeek={mapLatestWeeks.get(`${tourCity.id}:${tourPrimaryIntegration.codigo}`)} signal={mapSignals.get(tourCity.id)?.indicador===tourPrimaryIntegration.codigo?mapSignals.get(tourCity.id):undefined} onEngagementChange={engaged=>{tourPreviewEngaged.current=engaged;}} onSelect={()=>{pauseMapTour();selectMapIntegration(tourCity.id,tourPrimaryIntegration);}}/>}{hoveredCity && !pickedCity && <div className="municipality-tooltip" role="status" style={{ left: hoveredCity.x, top: hoveredCity.y }}><strong>{hoveredCity.name}</strong><span>São Paulo · IBGE {hoveredCity.id}</span><p>{mapTooltipMessage(hoveredCity)}</p></div>}{pickedCity && <MapCityPicker city={pickedCity} options={mapOptions} signal={mapSignals.get(pickedCity.id)} onClose={()=>setPickedCity(null)} onSelect={integration=>selectMapIntegration(pickedCity.id,integration)}/>}<p className="map-gesture-hint"><span className="mouse-gesture">Ctrl + scroll para ampliar</span><span className="touch-gesture">Use dois dedos para ampliar</span></p><div className="map-controls-dock">{activeMapRegion!==null&&<button type="button" className="secondary filter-trigger map-region-back" onClick={resetMapRegions} data-icon="arrowLeft"><ActionIcon name="arrowLeft"/>Todas as regiões</button>}<div className="map-zoom"><button aria-label="Ampliar mapa" disabled={zoom >= 10} onClick={() => changeZoom(1.3)} data-icon="zoomIn"><ActionIcon name="zoomIn"/></button><button aria-label="Reduzir mapa" disabled={zoom <= .1} onClick={() => changeZoom(1 / 1.3)} data-icon="zoomOut"><ActionIcon name="zoomOut"/></button><button className="map-reset" aria-label="Restaurar posição e zoom do mapa" title="Restaurar mapa" onClick={restoreMapAndTour}><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M8 3H3v5M16 3h5v5M3 16v5h5M21 16v5h-5"/><circle cx="12" cy="12" r="3"/></svg></button></div></div></div></section>
        <aside id="dashboard-right" className={`dashboard-right ${advancedPanels?'advanced':'compact'}`}>{hasSelectedMunicipality && (advancedPanels ? <><section className="card"><div className="section-heading"><h3>Fontes cadastradas</h3><span className="counter">{page.arquivadas?'…':page.count}</span></div>{loading || page.arquivadas ? <p role="status" className="muted">Carregando fontes…</p> : page.sources.length ? <SourceFeed page={page} onExpired={onLogout}/> : <div className="compact-empty"><span aria-hidden="true">↗</span><h3>Nenhuma fonte cadastrada</h3><p className="muted">Associe dados públicos a um município ou região.</p></div>}{canSources && <button className="text-button" onClick={() => { setTab('fontes'); setEditor('new'); }} data-icon="plus"><ActionIcon name="plus"/>Cadastrar fonte </button>}</section>{indicators&&<section className="card data-provenance"><div className="section-heading"><h3>Origem dos dados</h3></div><p><strong>{indicators.territorio.nome}</strong> · {indicators.agravo_nome}</p>{indicators.integracao&&<><p>{indicators.integracao.publicador} · Base: {indicators.integracao.base_original}</p><p>{indicators.integracao.indicador_nome} · {indicators.integracao.base_temporal}</p><p className="muted">{indicators.integracao.definicao}</p><a href={indicators.integracao.documentacao} target="_blank" rel="noreferrer">Metodologia da fonte ↗</a></>}<p>Período: {indicators.serie.length ? `${indicators.serie[0].data.split('-').reverse().join('/')} a ${indicators.serie.at(-1)!.data.split('-').reverse().join('/')}` : 'Sem dados no período'}</p><p>Coleta dos lotes exibidos: {indicators.coletado_em ? new Date(indicators.coletado_em).toLocaleString('pt-BR') : '—'}</p><p>Última consulta bem-sucedida à fonte: {indicators.atualidade.ultima_consulta_em ? new Date(indicators.atualidade.ultima_consulta_em).toLocaleString('pt-BR') : '—'}</p><p className="provenance-source-label">{indicators.fontes.length === 1 ? 'Fonte:' : 'Fontes:'}</p>{indicators.fontes.map(f=><p key={f.id}><a href={f.url} target="_blank" rel="noreferrer">{f.nome} ↗</a></p>)}<p>Processamento: {indicators.atualizado_em?new Date(indicators.atualizado_em).toLocaleString('pt-BR'):'Sem dados no período'}</p>{indicators.territorio.tipo==='regiao'&&<p>Agregação dos {indicators.municipios_cobertos} municípios coletados, de {indicators.municipios_regiao} na região. Não representa a região inteira quando a cobertura é parcial.</p>}</section>}</> : <><CompactOrigin data={indicators}/><CompactSeries data={indicators}/><CompactSources data={indicators}/></>)}</aside>
      </div></div>{hasSelectedMunicipality&&<TerritoryComparison context={indicators} onExpired={onLogout}/>}</>
      : tab === "ajuda" ? <HelpPage user={user}/> : tab === "administracao" ? (user.administrador ? <Administration user={user} onExpired={onLogout} onUserChanged={onUserChanged}/> : <p>Seu perfil não tem acesso à administração.</p>) : <><div className="page-heading"><div><span className="eyebrow">{canSources ? 'ADMINISTRAÇÃO' : 'CONSULTA'}</span><h1>Fontes de dados</h1><p className="muted">{canSources ? 'Gerencie a origem dos dados e os territórios monitorados.' : 'Consulte a origem dos dados e os territórios monitorados.'}</p></div><div className="source-heading-actions">{canSources && !editor && <button onClick={() => { setEditor('new'); setSuccess(''); }} data-icon="plus"><ActionIcon name="plus"/>Cadastrar fonte</button>}</div></div>{canSources && editor ?
 <SourceForm key={editor === 'new' ? 'new' : editor.id} source={editor === 'new' ? undefined : editor} onCancel={() => setEditor(null)} onExpired={onLogout} onSave={() => { setEditor(null); setSuccess('Fonte salva com sucesso.'); void load(); }} />
      : <section className="card source-list"><div className="section-heading"><h2>{showArchived?'Fontes arquivadas':'Origens cadastradas'}</h2><span className="counter">{page.arquivadas===showArchived ? page.count : '…'} {page.count === 1 ? 'fonte' : 'fontes'}</span></div>{canSources&&<div className="source-archive-tabs" role="group" aria-label="Filtrar fontes"><button type="button" className="secondary" aria-pressed={!showArchived} onClick={()=>setShowArchived(false)} data-icon="database"><ActionIcon name="database"/>Cadastradas</button><button type="button" className="secondary" aria-pressed={showArchived} onClick={()=>setShowArchived(true)} data-icon="archive"><ActionIcon name="archive"/>Arquivadas</button></div>}<div className="source-search"><label htmlFor="source-search">Pesquisar fontes</label><div className="source-search-field"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg><input id="source-search" type="search" maxLength={200} placeholder="Município, IBGE ou fonte" value={sourceSearch} onChange={event=>setSourceSearch(event.target.value)}/>{sourceSearch && <button type="button" className="secondary" onClick={()=>setSourceSearch('')} data-icon="close"><ActionIcon name="close"/>Limpar</button>}</div></div>{loading || page.arquivadas!==showArchived ? <p role="status">Carregando fontes…</p> : page.sources.length === 0 ? <div className="empty-state"><span className="empty-icon" aria-hidden="true">▤</span><h3>{sourceSearch.trim() ? 'Nenhuma fonte encontrada' : showArchived ? 'Nenhuma fonte arquivada' : 'Nenhuma fonte cadastrada'}</h3><p>{sourceSearch.trim() ? 'Tente outro município, código IBGE ou nome de fonte.' : showArchived ? 'As fontes arquivadas aparecerão aqui.' : canSources ? 'Adicione uma fonte pública para preparar o monitoramento.' : 'Aguarde o cadastro de fontes pelo administrador.'}</p>{canSources && !showArchived && !sourceSearch.trim() && <button className="secondary" onClick={() => setEditor('new')} data-icon="plus"><ActionIcon name="plus"/>Cadastrar primeira fonte</button>}</div> : <><div className="table-scroll"><table><thead><tr><th>Território / fonte</th><th>Formato</th><th>Situação</th><th>Última coleta</th><th><span className="sr-only">Ações</span></th></tr></thead><tbody>{page.sources.map(s => <tr key={s.id}><td><strong>{territoryLabel(s)}</strong><small>{sourcePeriodLabel(s)}</small><a href={s.url_coleta||s.url} target="_blank" rel="noreferrer">Ver fonte ↗</a></td><td data-label="Formato">{s.tipo.toUpperCase()}</td><td data-label="Situação"><span className={`badge ${s.ativa && !s.arquivada_em ? '' : 'inactive'}`}>{s.arquivada_em ? 'Arquivada' : s.ativa ? 'Habilitada' : 'Desabilitada'}</span>{!s.integracao&&<small>Sem integração automática</small>}</td><td data-label="Última coleta">{s.ultima_coleta_em ? new Date(s.ultima_coleta_em).toLocaleString('pt-BR') : s.coleta_inicial_status==='pendente' ? 'Coleta inicial agendada' : s.coleta_inicial_status==='executando' ? 'Coleta inicial em execução' : s.coleta_inicial_status==='erro' ? 'Falha na coleta inicial' : 'Não realizada'}{s.coleta_inicial_status==='erro'&&s.coleta_inicial_mensagem&&<small className="processing-error">{s.coleta_inicial_mensagem}</small>}{s.ultima_execucao && <small>{s.ultima_execucao.status === 'erro' ? 'Última tentativa falhou' : s.ultima_execucao.status === 'executando' ? 'Coleta em execução' : `${s.ultima_execucao.quantidade_registros} registros brutos`}</small>}{s.processamento&&<small className={s.processamento.status==='erro'?'processing-error':''}>{s.processamento.status==='erro'?`Falha no processamento: ${s.processamento.mensagem}`:`${s.processamento.registros} registros padronizados`}</small>}</td><td data-label="Ações"><div className="source-actions">{canCollect && s.coleta_disponivel && <button className="secondary" disabled={collecting !== null} onClick={() => void collect(s)} data-icon="play"><ActionIcon name="play"/>{collecting === s.id ? 'Coletando…' : 'Coletar agora'}</button>}<button className="secondary" onClick={() => void showHistory(s)} data-icon="history"><ActionIcon name="history"/>Histórico</button>{canSources && (s.arquivada_em ? <button className="secondary" aria-label={`Restaurar ${territoryLabel(s)}`} disabled={archiving!==null} onClick={()=>void archiveSource(s,false)} data-icon="restore"><ActionIcon name="restore"/>Restaurar</button> : <><button className="secondary" aria-label={`Editar ${territoryLabel(s)} · ${sourcePeriodLabel(s)}`} onClick={() => { setEditor(s); setSuccess(''); }} data-icon="edit"><ActionIcon name="edit"/>Editar</button><button className="secondary archive-danger" aria-label={`Arquivar ${territoryLabel(s)}`} disabled={archiving!==null||collecting===s.id} onClick={()=>void archiveSource(s,true)} data-icon="archive"><ActionIcon name="archive"/>Arquivar</button></>)}</div></td></tr>)}</tbody></table></div><div className="pagination"><button className="secondary" disabled={page.page <= 1} onClick={() => void load(page.page - 1)} data-icon="arrowLeft"><ActionIcon name="arrowLeft"/>Anterior</button><span>Página {page.page} de {page.pages}</span><button className="secondary" disabled={page.page >= page.pages} onClick={() => void load(page.page + 1)} data-icon="arrowRight"><ActionIcon name="arrowRight"/>Próxima</button></div></>}
      </section>}</>}
      </main></div>;

}

function ExportDataGate({user,data,onExpired}:{user:User;data:Indicators|null;onExpired:()=>void}) {
  return user.permissoes.includes("exportar_dados") ? <ExportData data={data} onExpired={onExpired}/> : null;
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
  useEffect(()=>{
    if(!user)return;
    const update=()=>{void api<{user:User}>('/auth/me/').then(result=>setUser(result.user)).catch(e=>{if(e instanceof ApiError&&e.status===401)setUser(null);});};
    window.addEventListener('focus',update);
    return()=>window.removeEventListener('focus',update);
  },[user?.id]);
  if (loading) return <main className="connection-screen" role="status"><Brand /><p>Conectando ao SME…</p></main>;
  if (error) return <main className="connection-screen"><Brand /><p role="alert">{error}</p><button onClick={() => void restore()} data-icon="refresh"><ActionIcon name="refresh"/>Tentar novamente</button></main>;
  return user ? <Workspace user={user} onUserChanged={setUser} onLogout={() => setUser(null)} /> : <Login onLogin={setUser} />;
}

createRoot(document.getElementById('root')!).render(<App />);
