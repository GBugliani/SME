"""Texto de alertas com valores suficientes para auditar a comparação."""


def decimal_pt(value):
    return str(value).replace('.', ',')


def alert_message(disease, observed, day, threshold):
    return (f'{disease}: {observed} casos na semana de {day:%d/%m/%Y}, '
            f'acima do limiar calculado de {decimal_pt(threshold)} casos. '
            'Sinal de possível surto para investigação; não confirma ocorrência.')
