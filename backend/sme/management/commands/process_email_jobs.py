import time
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from sme.email_alerts import run_next_email


class Command(BaseCommand):
    help = 'Envia avisos de alertas por SMTP; --loop acompanha a fila continuamente.'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true')

    def handle(self, *args, **options):
        while True:
            close_old_connections()
            try:
                delivery = run_next_email()
            except Exception as exc:
                if not options['loop']:
                    raise
                self.stderr.write(f'Fila de e-mail indisponível: {type(exc).__name__}')
                time.sleep(5)
                continue
            if delivery:
                self.stdout.write(f'Envio {delivery.pk}: {delivery.status}')
            elif not options['loop']:
                break
            else:
                time.sleep(5)
