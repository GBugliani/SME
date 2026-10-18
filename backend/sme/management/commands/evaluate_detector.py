"""Avaliação reproduzível a partir de um JSON público preservado, sem gravar no banco."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from sme.collection import InfoDengueAdapter, MUNICIPIOS_SP, CollectionError
from sme.detectors import MovingBaseline, MedianMAD


class Command(BaseCommand):
    help = 'Avalia os métodos com/sem histórico anterior ao ano, usando um JSON InfoDengue preservado.'

    def add_arguments(self, parser):
        parser.add_argument('--arquivo', required=True)
        parser.add_argument('--url', required=True)
        parser.add_argument('--municipio', required=True)
        parser.add_argument('--ano', required=True, type=int)
        parser.add_argument('--saida', required=True)

    def handle(self, *args, **options):
        try:
            code=options['municipio']
            if code not in MUNICIPIOS_SP:
                raise ValueError('Município inválido.')
            path=Path(options['arquivo'])
            if path.stat().st_size > 5*1024*1024:
                raise ValueError('O arquivo excede 5 MiB.')
            raw=path.read_bytes()
            source=SimpleNamespace(url=options['url'],tipo='json',recorte=SimpleNamespace(tipo='municipio',codigo=code,uf='SP',nome=MUNICIPIOS_SP[code]))
            points=InfoDengueAdapter().normalize(json.loads(raw), source)
            current=[p for p in points if p['ano']==options['ano']]
            available=[p for p in current if p['casos'] is not None]
            if not available:
                raise ValueError('Sem dados observados no ano solicitado.')
            peak=max(available,key=lambda p:p['casos'])
            results=[]
            for method in [MovingBaseline(),MedianMAD()]:
                for warmup in (False,True):
                    flags=[f for f in method.analyze(points if warmup else current) if current[0]['data']<=f['data']<=current[-1]['data']]
                    before=[f for f in flags if f['data']<=peak['data']]
                    results.append({'metodo':method.name,'versao_algoritmo':method.version,'parametros':method.parameters,
                        'historico_anterior':warmup,'semanas_sinalizadas':flags,
                        'pico_sinalizado':any(f['data']==peak['data'] for f in flags),
                        'primeiro_sinal_ate_pico':before[0]['data'] if before else None,
                        'antecedencia_semanas_ao_pico':(peak['data']-before[0]['data']).days//7 if before else None})
            report={'avaliado_em':timezone.now(),'url':source.url,'municipio':code,'ano':options['ano'],
                'sha256':hashlib.sha256(raw).hexdigest(),'pico_observado':peak,'resultados':results,
                'limites':'Retrospectiva de um episódio com dados revisados. Não mede sensibilidade/especificidade nem reproduz atrasos de notificação.'}
            Path(options['saida']).write_text(json.dumps(report,ensure_ascii=False,default=str,indent=2),encoding='utf-8')
            self.stdout.write(f'Avaliação salva em {options["saida"]}. Pico: {peak["data"]}; {peak["casos"]} casos.')
        except (ValueError, OSError, CollectionError) as exc:
            raise CommandError(str(exc)) from exc
