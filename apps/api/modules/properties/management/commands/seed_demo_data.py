"""Jeu de données de démonstration.

Crée 5 propriétaires (2 maisons chacun), 10 locataires (1 par maison, liés
par un bail actif) et 2 copropriétaires. Chaque propriétaire possède au
moins un locataire. Commande idempotente : les comptes existants sont
réutilisés par numéro de téléphone. Utilisation :

    python manage.py seed_demo_data
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from django.conf import settings

from modules.accounts.phones import normalize_e164
from modules.leases.models import Lease, Tenant
from modules.properties.models import Ownership, Property
from modules.subscriptions.models import Subscription, SubscriptionPlan

User = get_user_model()

PASSWORD = "DemoImmoLib2026!"

OWNERS = [
    ("+2250101010101", "Jean-Marc", "Kouassi"),
    ("+2250102020202", "Awa", "Diop"),
    ("+2250103030303", "Ibrahim", "Traore"),
    ("+2250104040404", "Nadine", "Bamba"),
    ("+2250105050505", "Serge", "Gnakpa"),
]

CO_OWNERS = [
    ("+2250601010101", "Clarisse", "Nguessan"),
    ("+2250602020202", "Abdoulaye", "Sangare"),
]

HOUSES = [
    ("Villa Cocody", "Rue des Jardins, Lot 12", "Abidjan", "Cocody"),
    ("Villa Riviera", "Boulevard Latrille", "Abidjan", "Riviera Golf"),
    ("Maison Yopougon", "Rue du Marché, Lot 45", "Abidjan", "Yopougon"),
    ("Villa Marcory", "Avenue 12, Quartier Résidentiel", "Abidjan", "Marcory"),
    ("Villa Koumassi", "Rue des Palmiers", "Abidjan", "Koumassi"),
    ("Maison Treichville", "Rue du Commerce", "Abidjan", "Treichville"),
    ("Villa Bingerville", "Route de la Corniche", "Abidjan", "Bingerville"),
    ("Maison Port-Bouët", "Rue de l'Aéroport", "Abidjan", "Port-Bouët"),
    ("Villa Adjame", "Rue des Brasseries", "Abidjan", "Adjame"),
    ("Villa Abobo", "Rue du Centre", "Abidjan", "Abobo"),
]

TENANTS = [
    ("Konan", "Aya", "+2250701010101", "aya.konan@example.com", "70000", "5"),
    ("Ouattara", "Moussa", "+2250702020202", "moussa.ouattara@example.com", "85000", "7"),
    ("Diallo", "Fatou", "+2250703030303", "fatou.diallo@example.com", "95000", "3"),
    ("Koffi", "Yao", "+2250704040404", "yao.koffi@example.com", "75000", "10"),
    ("Soro", "Mariam", "+2250705050505", "mariam.soro@example.com", "65000", "1"),
    ("N'Guessan", "Kouadio", "+2250706060606", "kouadio.nguessan@example.com", "80000", "8"),
    ("Bamba", "Adjoua", "+2250707070707", "adjoua.bamba@example.com", "90000", "5"),
    ("Traore", "Seydou", "+2250708080808", "seydou.traore@example.com", "70000", "12"),
    ("Dje", "Mireille", "+2250709090909", "mireille.dje@example.com", "110000", "3"),
    ("Zadi", "Emmanuel", "+2250710101010", "emmanuel.zadi@example.com", "85000", "6"),
]


class Command(BaseCommand):
    help = "Cree un jeu de donnees de demonstration : 5 proprietaires, 10 locataires, 2 coproprietaires."

    def _get_or_create_user(self, phone, first_name, last_name):
        phone = normalize_e164(phone)
        user = User.objects.filter(phone=phone).first()
        if user is None:
            user = User.objects.create_user(
                phone=phone,
                password=PASSWORD,
                first_name=first_name,
                last_name=last_name,
            )
        else:
            updates = {}
            if first_name and user.first_name != first_name:
                updates["first_name"] = first_name
            if last_name and user.last_name != last_name:
                updates["last_name"] = last_name
            if updates:
                updates["updated_at"] = timezone.now()
                User.objects.filter(id=user.id).update(**updates)
                user.refresh_from_db()
        return user

    def _ensure_pro_plan(self, user):
        defaults = settings.SUBSCRIPTION_PLAN_DEFAULTS["pro"]
        pro_plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="pro",
            defaults={
                "name": defaults["name"],
                "description": defaults["description"],
                "price_monthly": defaults["price_monthly"],
                "currency": settings.SUBSCRIPTION_CURRENCY,
                "max_houses": defaults["max_houses"],
                "features": defaults["features"],
            },
        )
        subscription, _ = Subscription.objects.get_or_create(
            user=user,
            defaults={"plan": pro_plan},
        )
        if subscription.plan_id != pro_plan.id:
            subscription.plan = pro_plan
            subscription.save(update_fields=["plan", "updated_at"])

    def _create_property(self, name, address, city, commune, owner):
        house = Property.objects.create(
            name=name,
            address=address,
            city=city,
            commune=commune,
        )
        Ownership.objects.create(
            property=house,
            user=owner,
            role=Ownership.Role.PRIMARY,
            access_level=Ownership.AccessLevel.ACTIVE,
            ownership_percentage=Decimal("100"),
        )
        return house

    def _create_tenant(self, house, owner, full_name, phone, email):
        phone = normalize_e164(phone)
        tenant = Tenant(
            property=house,
            full_name=full_name,
            phone=phone,
            email=email,
            created_by=owner,
        )
        tenant.full_clean()
        tenant.save()
        return tenant

    def _create_active_lease(self, house, tenant, owner, rent, due_day):
        lease = Lease(
            property=house,
            tenant=tenant,
            status=Lease.Status.ACTIVE,
            start_date=date.today() - timedelta(days=180),
            monthly_rent=Decimal(rent),
            monthly_charges=Decimal("5000"),
            due_day=int(due_day),
            security_deposit=Decimal(rent) * 2,
            rent_advance=Decimal(rent),
            created_by=owner,
            activated_at=timezone.now(),
        )
        lease.full_clean()
        lease.save()
        house.status = Property.Status.OCCUPIED
        house.save(update_fields=["status", "updated_at"])
        return lease

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Le jeu de données de démonstration est réservé au mode DEBUG."
            )
        owners = []
        for phone, first_name, last_name in OWNERS:
            owner = self._get_or_create_user(phone, first_name, last_name)
            self._ensure_pro_plan(owner)
            owners.append(owner)

        co_owners = [
            self._get_or_create_user(phone, first_name, last_name)
            for phone, first_name, last_name in CO_OWNERS
        ]

        houses = []
        for index, (name, address, city, commune) in enumerate(HOUSES):
            owner = owners[index // 2]
            house = Property.objects.filter(
                name=name, address=address, city=city
            ).first()
            if house is None:
                house = self._create_property(name, address, city, commune, owner)
            houses.append(house)

        for index, (last_name, first_name, phone, email, rent, due_day) in enumerate(
            TENANTS
        ):
            house = houses[index]
            owner = owners[index // 2]
            tenant = Tenant.objects.filter(property=house, phone=phone).first()
            if tenant is None:
                tenant = self._create_tenant(
                    house, owner, f"{first_name} {last_name}", phone, email
                )
            lease = Lease.objects.filter(property=house, tenant=tenant).first()
            if lease is None:
                self._create_active_lease(house, tenant, owner, rent, due_day)

        co_owner_sets = {
            co_owners[0]: houses[0:4],
            co_owners[1]: houses[4:8],
        }
        for co_owner, assigned_houses in co_owner_sets.items():
            for house in assigned_houses:
                Ownership.objects.get_or_create(
                    property=house,
                    user=co_owner,
                    defaults={
                        "role": Ownership.Role.CO_OWNER,
                        "access_level": Ownership.AccessLevel.ACTIVE,
                        "ownership_percentage": Decimal("20"),
                    },
                )
                primary = house.ownerships.get(role=Ownership.Role.PRIMARY)
                primary.ownership_percentage = Decimal("80")
                primary.save(update_fields=["ownership_percentage"])

        self.stdout.write(
            self.style.SUCCESS(
                "Donnees de demonstration creees : "
                f"{len(owners)} proprietaires, {len(houses)} maisons, "
                f"{len(TENANTS)} locataires, {len(co_owners)} coproprietaires. "
                f"Mot de passe commun : {PASSWORD}"
            )
        )
