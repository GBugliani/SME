import type {ReactNode, SVGProps} from 'react';

export type ActionIconName = 'home'|'database'|'users'|'shield'|'activity'|'mail'|'history'|'close'|'save'|'plus'|'edit'|'key'|'arrowLeft'|'arrowRight'|'refresh'|'send'|'check'|'search'|'filter'|'download'|'eye'|'eyeOff'|'logout'|'archive'|'restore'|'trash'|'play'|'help'|'zoomIn'|'zoomOut'|'list'|'settings'|'pause'|'bell'|'external';

const paths: Record<ActionIconName, ReactNode> = {
  home: <><path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/><path d="M9 21v-7h6v7"/></>,
  database: <><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5M3 12c0 1.7 4 3 9 3s9-1.3 9-3"/></>,
  users: <><circle cx="9" cy="8" r="3"/><path d="M2 20v-2a7 7 0 0 1 14 0v2M16 5a3 3 0 0 1 0 6m2 3a6 6 0 0 1 4 6"/></>,
  shield: <><path d="m12 2 9 4v6c0 5-3.5 8-9 10-5.5-2-9-5-9-10V6z"/><path d="m9 12 2 2 4-4"/></>,
  activity: <path d="M2 12h4l3-7 5 14 3-7h5"/>,
  mail: <><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m3 6 9 7 9-7"/></>,
  history: <><path d="M3 11a9 9 0 1 1 2 6M3 4v7h7"/><path d="M12 7v5l3 2"/></>,
  close: <path d="M5 5 19 19M19 5 5 19"/>,
  save: <><path d="M4 3h14l3 3v15H3V3zM7 3v7h10V3M7 21v-8h10v8"/></>,
  plus: <path d="M12 4v16M4 12h16"/>,
  edit: <><path d="m4 20 4-.8L20 7a2 2 0 0 0-3-3L5 16zM15 6l3 3"/></>,
  key: <><circle cx="8" cy="15" r="5"/><path d="m12 11 9-9m-4 0 4 4m-6 0 3 3"/></>,
  arrowLeft: <path d="m14 5-7 7 7 7M7 12h14"/>,
  arrowRight: <path d="m10 5 7 7-7 7M3 12h14"/>,
  refresh: <><path d="M20 7a9 9 0 0 0-15-1L3 8M4 17a9 9 0 0 0 15 1l2-2M3 3v5h5M21 21v-5h-5"/></>,
  send: <><path d="m22 2-8 20-4-8-8-4zM10 14 22 2"/></>,
  check: <path d="m4 12 5 5L20 6"/>,
  search: <><circle cx="10.5" cy="10.5" r="7"/><path d="m16 16 5 5"/></>,
  filter: <><path d="M3 5h18l-7 8v6l-4 2v-8z"/></>,
  download: <><path d="M12 3v13m-5-5 5 5 5-5M3 19v2h18v-2"/></>,
  eye: <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></>,
  eyeOff: <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/><path d="m3 3 18 18"/></>,
  logout: <><path d="M10 3H4a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h6M14 7l5 5-5 5m5-5H9"/></>,
  archive: <><rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v11h14V9m-9 5h4"/></>,
  restore: <><path d="M3 11a9 9 0 1 1 2 6M3 4v7h7"/><path d="M12 7v9m-4-4 4 4 4-4"/></>,
  trash: <><path d="M4 6h16M9 6V3h6v3m3 0-1 15H7L6 6m4 4v7m4-7v7"/></>,
  play: <path d="m8 4 12 8-12 8z"/>,
  help: <><circle cx="12" cy="12" r="10"/><path d="M9 9a3 3 0 1 1 5 2c-2 1-2 2-2 4m0 3h.01"/></>,
  zoomIn: <><circle cx="10" cy="10" r="7"/><path d="m15 15 6 6M10 6v8M6 10h8"/></>,
  zoomOut: <><circle cx="10" cy="10" r="7"/><path d="m15 15 6 6M6 10h8"/></>,
  list: <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="m10 2-.5 2.5-2 1-2.5-1-2 3 2 2-.2 2.5-2.3 1.5 1 3.5 2.8-.2 1.8 1.8L8 21h4l.5-2.5 2-1 2.5 1 2-3-2-2 .2-2.5 2.3-1.5-1-3.5-2.8.2-1.8-1.8L14 2z"/></>,
  pause: <path d="M8 5v14M16 5v14"/>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M9 21h6"/></>,
  external: <><path d="M13 4h7v7M20 4l-9 9M20 14v6H4V4h6"/></>,
};

export function ActionIcon({name,...props}: {name: ActionIconName}&SVGProps<SVGSVGElement>) {
  return <svg className="action-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" {...props}>{paths[name]}</svg>;
}
