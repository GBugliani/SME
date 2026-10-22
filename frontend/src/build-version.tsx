declare const __SME_BUILD_INFO__: {
  version: string;
  builtAt: string;
};

const build = __SME_BUILD_INFO__;
const builtAt = new Intl.DateTimeFormat('pt-BR', {
  dateStyle: 'short',
  timeStyle: 'short',
  timeZone: 'America/Sao_Paulo',
}).format(new Date(build.builtAt));

export function BuildVersion() {
  return <span className="build-version" title="Versão do SME e horário da compilação">
    SME v{build.version} · compilado em {builtAt}
  </span>;
}
