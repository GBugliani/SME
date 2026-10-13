from django.core.management.base import BaseCommand, CommandError
from sme.models import LoteColeta
from sme.processing import process_lote


class Command(BaseCommand):
    help = 'Valida e processa os lotes brutos preservados no banco, do mais antigo ao mais recente.'
    def handle(self, *args, **options):
        failed = 0
        for lote_id in LoteColeta.objects.order_by('criada_em','pk').values_list('pk',flat=True):
            result = process_lote(lote_id)
            self.stdout.write(f'Lote {lote_id}: {result.status}, {result.quantidade_registros} registros. {result.mensagem}')
            failed += result.status=='erro'
        if failed:
            raise CommandError(f'{failed} lotes com falha de processamento; dados brutos preservados.')
