"""Creation du premier administrateur ImmoLib.

Operation reservee au serveur : aucun utilisateur ne peut devenir admin en
modifiant son profil. Utilisation :

    python manage.py create_admin --phone +2250707070707 --password "..." \
        --email admin@immolib.ci --first-name Admin --last-name ImmoLib

Pour promouvoir un compte existant (sans reinitialiser son mot de passe) :

    python manage.py create_admin --phone +2250707070707 --promote
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from modules.accounts.phones import normalize_e164

User = get_user_model()


class Command(BaseCommand):
    help = "Cree ou promeut un compte avec le role systeme ADMIN."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--phone", required=True, help="Telephone E.164 du compte.")
        parser.add_argument("--password", default="", help="Mot de passe (obligatoire pour un nouveau compte).")
        parser.add_argument("--email", default="", help="Adresse email du compte.")
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")
        parser.add_argument(
            "--promote",
            action="store_true",
            help="Promouvoir un compte existant (trouve par telephone) sans creer.",
        )

    def handle(self, *args, **options) -> None:
        phone = normalize_e164(options["phone"])
        user = User.objects.filter(phone=phone).first()
        if user is None and options["promote"]:
            raise CommandError(f"Aucun compte avec le telephone {phone}. --promote sans --password cree le compte.")
        if user is not None:
            user.role = User.Role.ADMIN
            if options["email"]:
                user.email = options["email"]
            if options["first_name"]:
                user.first_name = options["first_name"]
            if options["last_name"]:
                user.last_name = options["last_name"]
            user.save(update_fields=["role", "email", "first_name", "last_name", "updated_at"])
            self.stdout.write(
                self.style.SUCCESS(f"Compte {phone} promu administrateur (role ADMIN).")
            )
            return
        if not options["password"]:
            raise CommandError("Un mot de passe est obligatoire pour creer un nouveau compte admin.")
        try:
            validate_password(options["password"])
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        User.objects.create_user(
            phone=phone,
            password=options["password"],
            role=User.Role.ADMIN,
            email=options["email"],
            first_name=options["first_name"],
            last_name=options["last_name"],
        )
        self.stdout.write(
            self.style.SUCCESS(f"Administrateur cree : {phone} (role ADMIN).")
        )
