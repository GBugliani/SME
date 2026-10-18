"""Estratégias semanais causais: nunca incluem a semana analisada na referência."""
import math
import pandas as pd

PARAMETERS = {'janela': 8, 'desvios': 3.0, 'razao_minima': 2.0, 'piso': 5.0}
METHODS = {
    'media_movel': {'nome': 'Média móvel e desvio padrão', 'versao_algoritmo': 1,
        'padrao': PARAMETERS, 'descricao': 'Maior valor entre média + desvios × desvio padrão, razão × média e piso.'},
    'mediana_mad': {'nome': 'Mediana e desvio absoluto mediano', 'versao_algoritmo': 1,
        'padrao': {'janela':8, 'fator_mad':3.0, 'razao_minima':2.0, 'piso':5.0},
        'descricao': 'Maior valor entre mediana + fator × 1,4826 × MAD, razão × mediana e piso.'},
}


def validate_parameters(method, parameters):
    if method not in METHODS or not isinstance(parameters, dict) or set(parameters) != set(METHODS[method]['padrao']):
        raise ValueError('Selecione um método e seus parâmetros disponíveis.')
    for key, value in parameters.items():
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('Os parâmetros devem ser números finitos.')
        if key == 'janela' and (type(value) is not int or not 4 <= value <= 52):
            raise ValueError('A janela deve conter de 4 a 52 semanas inteiras.')
        if key in ('desvios', 'fator_mad') and not .1 <= value <= 10:
            raise ValueError('O multiplicador deve estar entre 0,1 e 10.')
        if key == 'razao_minima' and not 1 <= value <= 10:
            raise ValueError('A razão mínima deve estar entre 1 e 10.')
        if key == 'piso' and not 0 <= value <= 1_000_000:
            raise ValueError('O piso deve estar entre zero e um milhão de casos.')
    return dict(parameters)


class MovingBaseline:
    name = 'media_movel'
    version = 1

    def __init__(self, parameters=None):
        self.parameters = validate_parameters(self.name, dict(parameters if parameters is not None else METHODS[self.name]['padrao']))

    def baseline(self, past):
        return past.mean(), past.std(ddof=0) * self.parameters['desvios']

    def analyze(self, points):
        if not points:
            return []
        frame = pd.DataFrame(points).set_index('data')
        frame.index = pd.to_datetime(frame.index)
        frame = frame.reindex(pd.date_range(frame.index.min(), frame.index.max(), freq='7D'))
        values = pd.to_numeric(frame['casos'], errors='coerce')
        past = values.shift(1).rolling(self.parameters['janela'], min_periods=self.parameters['janela'])
        baseline, spread = self.baseline(past)
        threshold = pd.concat([baseline + spread, baseline * self.parameters['razao_minima'],
            pd.Series(self.parameters['piso'], index=frame.index)], axis=1).max(axis=1)
        return [{'data': day.date(), 'observado': int(values.loc[day]), 'referencia': float(baseline.loc[day]),
                 'limiar': float(threshold.loc[day])} for day in frame.index
                if pd.notna(baseline.loc[day]) and pd.notna(values.loc[day]) and values.loc[day] > threshold.loc[day]]


class MedianMAD(MovingBaseline):
    name = 'mediana_mad'

    def baseline(self, past):
        return past.median(), past.apply(lambda a: abs(a - a.median()).median(), raw=False) * 1.4826 * self.parameters['fator_mad']


def strategy(method, parameters, version=1):
    if version != 1:
        raise ValueError('A versão do algoritmo não está disponível neste servidor.')
    validate_parameters(method, parameters)
    return {'media_movel': MovingBaseline, 'mediana_mad': MedianMAD}[method](parameters)
