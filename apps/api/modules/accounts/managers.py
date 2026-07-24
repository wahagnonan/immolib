from django.contrib.auth.base_user import BaseUserManager
from django.utils import timezone

from .phones import normalize_e164


class UserManager(BaseUserManager):
    """Cree les utilisateurs a partir du numero de telephone."""

    use_in_migrations = True

    def create_user(self, phone: str, password: str | None = None, **extra_fields):
        if not phone:
            raise ValueError("Le numero de telephone est obligatoire.")

        # Les comptes crees par l'administration ou les services internes sont
        # consideres verifies. L'inscription publique passe explicitement None.
        extra_fields.setdefault("phone_verified_at", timezone.now())
        user = self.model(phone=normalize_e164(phone), **extra_fields)
        user.set_password(password)
        user.full_clean(exclude=["password"])
        user.save(using=self._db)
        return user

    def create_superuser(self, phone: str, password: str, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Un superutilisateur doit avoir is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Un superutilisateur doit avoir is_superuser=True.")

        return self.create_user(phone, password, **extra_fields)
