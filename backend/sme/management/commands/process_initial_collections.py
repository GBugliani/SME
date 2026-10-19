import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from sme.initial_collection import enqueue_uncollected_sources, run_next_initial_collection


class Command(BaseCommand):
    help = 'Processa a primeira coleta das fontes habilitadas; --loop acompanha a fila.'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true')

    def handle(self, *args, **options):
        while True:
            close_old_connections()
            try:
                enqueue_uncollected_sources()
                job = run_next_initial_collection()
            except Exception as exc:
                if not options['loop']:
                    raise
                self.stderr.write(f'Fila de coleta inicial indisponível: {type(exc).__name__}')
                time.sleep(5)
                continue
            if job:
                self.stdout.write(f'Coleta inicial {job.pk}: {job.status}')
            elif not options['loop']:
                break
            else:
                time.sleep(5)
