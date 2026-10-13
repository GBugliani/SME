from getpass import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction


class Command(BaseCommand):
    help = "Cria interativamente um usuário comum, sem acesso administrativo."

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            while True:
                email = input("E-mail: ").strip().lower()
                user = User(email=email, is_staff=False, is_superuser=False, is_active=True)
                user.set_unusable_password()
                try:
                    user.full_clean()
                except ValidationError as exc:
                    self.stderr.write(" ".join(exc.messages))
                    continue
                break

            while True:
                password = getpass("Senha: ")
                confirmation = getpass("Senha (novamente): ")
                if password != confirmation:
                    self.stderr.write("As senhas não coincidem. Tente novamente.")
                    continue
                try:
                    validate_password(password, user)
                except ValidationError as exc:
                    self.stderr.write(" ".join(exc.messages))
                    continue
                break

            user.set_password(password)
            with transaction.atomic():
                user.save()
        except (KeyboardInterrupt, EOFError):
            raise CommandError("Criação cancelada. Nenhum usuário foi criado.")
        except IntegrityError:
            raise CommandError("Este e-mail já está cadastrado. Nenhum usuário foi criado.")
        self.stdout.write(self.style.SUCCESS("Usuário comum criado com sucesso."))
