"""Contratos estáveis. Alterar a definição exige uma nova chave/versão."""
from urllib.parse import parse_qs, urlsplit

SIVEP_URL = 'https://gitlab.com/cgcovid/dados-publicos/-/tree/main/Dados%20unificados/Unificado%20Srag'

INFOGRIPE_URL = 'https://raw.githubusercontent.com/infogripe/Boletim_InfoGripe/main/Dados/InfoGripe/capitais_serie_estimativas_tendencia_sem_filtro_febre.csv'
DISEASES = {'dengue': 'Dengue', 'chikungunya': 'Chikungunya', 'zika': 'Zika', 'srag': 'SRAG'}
DATASETS = {
    f'infodengue_{code}': {
        'codigo': f'infodengue_{code}', 'provedor': 'infodengue', 'publicador': 'InfoDengue',
        'base_original': 'SINAN', 'agravo': code, 'agravo_nome': DISEASES[code],
        'indicador_nome': 'Casos notificados', 'unidade': 'casos', 'frequencia': 'semanal',
        'base_temporal': 'Semana epidemiológica do InfoDengue', 'base_territorial': 'Município da API InfoDengue',
        'definicao': 'Notificações semanais; estimativas mantidas separadamente.',
        'versao': 'infodengue_v1', 'formato': 'json', 'municipios': 'SP',
        'documentacao': 'https://info.dengue.mat.br/services/api',
    } for code in ('dengue', 'chikungunya', 'zika')
}
DATASETS['infogripe_srag'] = {
    'codigo': 'infogripe_srag', 'provedor': 'infogripe', 'publicador': 'InfoGripe / Fiocruz',
    'base_original': 'SIVEP-Gripe', 'agravo': 'srag', 'agravo_nome': 'SRAG',
    'indicador_nome': 'Casos reportados', 'unidade': 'casos', 'frequencia': 'semanal',
    'base_temporal': 'Semana de início dos sintomas', 'base_territorial': 'Município de residência',
    'definicao': 'Série das capitais, sem filtro de febre, escala casos e grupo jurídico 0. Estimativas separadas.',
    'versao': 'infogripe_v1', 'formato': 'csv', 'municipios': ['3550308'],
    'documentacao': 'https://github.com/infogripe/Boletim_InfoGripe/blob/main/Dados/InfoGripe/readme.md',
}


DATASETS['sivep_srag'] = {
    'codigo': 'sivep_srag', 'provedor': 'sivep', 'publicador': 'SIVEP-Gripe / Ministério da Saúde',
    'base_original': 'SIVEP-Gripe', 'agravo': 'srag', 'agravo_nome': 'SRAG',
    'indicador_nome': 'Casos reportados', 'unidade': 'casos', 'frequencia': 'semanal',
    'base_temporal': 'Semana de início dos sintomas', 'base_territorial': 'Município de residência',
    'definicao': 'SRAG total: hospitalizações e óbitos independentemente de hospitalização. Semanas ausentes ficam sem dados, não zero. Ano escolhido no cadastro.',
    'versao': 'sivep_v1', 'formato': 'xlsx', 'municipios': 'SP',
    'documentacao': 'https://gitlab.com/cgcovid/dados-publicos/-/blob/main/Dados%20unificados/README.md',
}


def infer_dataset(url):
    """Compatibilidade para cadastros antigos; validação completa cabe ao adaptador."""
    parsed = urlsplit(url)
    if parsed.hostname == 'info.dengue.mat.br' and parsed.path == '/api/alertcity':
        code = 'infodengue_' + parse_qs(parsed.query).get('disease', [''])[0]
        return code if code in DATASETS else ''
    if url.startswith(SIVEP_URL + '?ano='):
        return 'sivep_srag'
    return 'infogripe_srag' if url == INFOGRIPE_URL else ''


def source_dataset(source):
    return getattr(source, 'indicador', '') or infer_dataset(source.url)
