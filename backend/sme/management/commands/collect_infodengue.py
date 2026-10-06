from django.core.management.base import BaseCommand, CommandError
from sme.collection import collect_source, collect_pilot, CollectionError
from sme.models import FonteEpidemiologica


class Command(BaseCommand):
    help = "Coleta dados brutos do piloto InfoDengue (dengue/São Paulo)."

    def add_arguments(self, parser):
        parser.add_argument("--source", type=int, help="ID de uma fonte cadastrada; sem ID coleta todas as fontes compatíveis.")

    def handle(self, *args, **options):
        try:
            runs = [collect_source(options["source"])] if options["source"] else collect_pilot(origin="manual")
        except (CollectionError, FonteEpidemiologica.DoesNotExist) as exc:
            raise CommandError(str(exc))
        if not runs:
            self.stdout.write("Nenhuma fonte ativa compatível disponível para coleta.")
        for run in runs:
            self.stdout.write(f"Fonte {run.fonte_id}: {run.status}, {run.quantidade_registros} registros. {run.mensagem}")
        if any(run.status == "erro" for run in runs):
            raise CommandError("Uma ou mais fontes falharam; consulte o histórico da coleta.")
