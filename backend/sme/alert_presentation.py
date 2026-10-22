"""Texto de alertas com valores suficientes para auditar a comparação."""


def decimal_pt(value):
    # str(float) preserva a precisão necessária para recuperar o valor usado
    # na comparação; arredondar aqui pode transformar 6 > 5,97 em 6 > 6.
    return str(value).replace('.', ',')


def alert_message(disease, observed, day, threshold):
    return (f'{disease}: {observed} casos na semana de {day:%d/%m/%Y}, '
            f'acima do limiar calculado de {decimal_pt(threshold)} casos. '
            'Sinal de possível surto para investigação; não confirma ocorrência.')
