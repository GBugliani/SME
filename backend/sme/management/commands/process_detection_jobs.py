import time
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from sme.detection import run_next_job


class Command(BaseCommand):
    help = 'Executa reanálises versionadas pendentes; --loop acompanha a fila continuamente.'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true')

    def handle(self, *args, **options):
        while True:
            close_old_connections()
            try:
                job = run_next_job()
            except Exception as exc:
                if not options['loop']:
                    raise
                self.stderr.write(f'Fila de detecção indisponível: {type(exc).__name__}')
                time.sleep(5)
                continue
            if job:
                self.stdout.write(f'Reanálise {job.pk}: {job.status}; {job.processados}/{job.total}')
            elif not options['loop']:
                break
            else:
                time.sleep(5)
