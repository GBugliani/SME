declare const __SME_BUILD_INFO__: {
  version: string;
  revision: string;
  builtAt: string;
};

const build = __SME_BUILD_INFO__;
const builtAt = new Intl.DateTimeFormat('pt-BR', {
  dateStyle: 'short',
  timeStyle: 'short',
  timeZone: 'America/Sao_Paulo',
}).format(new Date(build.builtAt));

export function BuildVersion() {
  return <span className="build-version" title="Identificador do código da aplicação e horário da compilação">
    SME v{build.version} · código {build.revision} · compilado em {builtAt}
  </span>;
}
