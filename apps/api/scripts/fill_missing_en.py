"""Complete les traductions EN manquantes du catalogue django.po."""
from pathlib import Path

import polib

PO = Path(__file__).resolve().parent.parent / "locale" / "en" / "LC_MESSAGES" / "django.po"

TRANSLATIONS = {
    "Role systeme. Seul le role ADMIN ouvre l'espace d'administration. Le statut bailleur ou locataire reste derive des donnees.":
        "System role. Only the ADMIN role opens the administration area. The landlord or tenant status remains derived from the data.",
    "Un compte utilise déjà cette adresse email.":
        "An account already uses this email address.",
    "Trop de tentatives échouées. Réessayez dans quelques minutes.":
        "Too many failed attempts. Try again in a few minutes.",
    "Connexion admin": "Admin login",
    "Utilisateur suspendu": "User suspended",
    "Utilisateur reactive": "User reactivated",
    "Role utilisateur modifie": "User role changed",
    "Abonnement modifie": "Subscription changed",
    "Abonnement annule": "Subscription cancelled",
    "Abonnement prolonge": "Subscription extended",
    "Abonnement active": "Subscription activated",
    "administrateur": "administrator",
    "Vous ne pouvez pas suspendre votre propre compte.":
        "You cannot suspend your own account.",
    "Un compte administrateur ne peut pas être suspendu par ce canal.":
        "An administrator account cannot be suspended through this channel.",
    "Ce compte est deja %s.": "This account is already %s.",
    "suspendu": "suspended",
    "Ce plan n'existe pas ou n'est plus disponible.":
        "This plan does not exist or is no longer available.",
    "Le nombre de jours doit etre positif.": "The number of days must be positive.",
    "La duree doit etre positive.": "The duration must be positive.",
    "Tu ne peux pas préparer un paiement pour cette maison.":
        "You cannot prepare a payment for this house.",
    "Seul un bail actif peut recevoir un paiement.":
        "Only an active lease can receive a payment.",
    "Indique le premier et le dernier mois à payer.":
        "Provide the first and last month to pay.",
    "Les périodes doivent commencer le premier du mois.":
        "Periods must start on the first of the month.",
    "Le dernier mois doit suivre le premier mois.":
        "The last month must come after the first month.",
    "Sélectionne une caution ou au moins un mois de loyer.":
        "Select a security deposit or at least one month of rent.",
    "Paiement à confirmer": "Payment to confirm",
    "Paiement confirmé": "Payment confirmed",
    "Le contenu du code de compte n’est plus disponible.":
        "The account code content is no longer available.",
    "Bonjour {tenant}, {owner} vous invite à rejoindre ImmoLib pour le bien {house}. Créez ou rattachez votre compte ici : {url} (invitation valable jusqu'au {expires_at}).":
        "Hello {tenant}, {owner} invites you to join ImmoLib for the property {house}. Create or link your account here: {url} (invitation valid until {expires_at}).",
    "Bonjour {payee}, le locataire {tenant} a initie un paiement de {amount} par {operator} ({phone}) pour {house} ({period}). Verifiez la reception puis confirmez dans ImmoLib : reference {reference}.":
        "Hello {payee}, the tenant {tenant} initiated a payment of {amount} via {operator} ({phone}) for {house} ({period}). Check that you received it, then confirm in ImmoLib: reference {reference}.",
    "Bonjour {tenant}, le bailleur a confirme votre paiement de {amount} pour {house} ({period}). Votre quittance est disponible dans ImmoLib : reference {reference}.":
        "Hello {tenant}, the landlord confirmed your payment of {amount} for {house} ({period}). Your rent receipt is available in ImmoLib: reference {reference}.",
    "Le contenu du code n’est plus disponible.":
        "The code content is no longer available.",
    "Bien": "Property",
    "Le paiement ne possède aucune affectation.":
        "The payment has no allocation.",
    "Tu ne peux pas modifier ce bien.":
        "You cannot modify this property.",
    "Un bien indisponible ne peut pas etre loue.":
        "An unavailable property cannot be leased.",
    "Ce bien possede deja un bail actif.":
        "This property already has an active lease.",
    "Tu ne peux pas enregistrer un paiement pour ce bien.":
        "You cannot record a payment for this property.",
    "Les paiements depassent le montant de l'echeance.":
        "Payments exceed the amount of the due item.",
    "Le paiement doit être affecté à au moins une obligation.":
        "The payment must be allocated to at least one obligation.",
    "Une obligation ne peut apparaître qu'une seule fois.":
        "An obligation can only appear once.",
    "Une obligation de paiement est introuvable.":
        "A payment obligation could not be found.",
    "Toutes les obligations doivent utiliser la même devise.":
        "All obligations must use the same currency.",
    "Moyen de paiement hors ImmoLib invalide.":
        "Invalid off-platform payment method.",
    "Le montant doit etre strictement positif.":
        "The amount must be strictly positive.",
    "Ce paiement n'appartient pas a ce locataire.":
        "This payment does not belong to this tenant.",
    "Un paiement annule ne peut pas etre confirme.":
        "A cancelled payment cannot be confirmed.",
    "Un paiement annule ne peut pas etre conteste.":
        "A cancelled payment cannot be disputed.",
    "Le motif de contestation est obligatoire.":
        "A dispute reason is required.",
    "Le motif d'annulation est obligatoire.":
        "A cancellation reason is required.",
    "Cette obligation n'est pas une caution.":
        "This obligation is not a security deposit.",
    "Type de mouvement de caution invalide.":
        "Invalid security deposit movement type.",
    "Le montant doit être strictement positif.":
        "The amount must be strictly positive.",
    "Le motif de la retenue est obligatoire.":
        "A retention reason is required.",
    "Sélectionnez le loyer à solder.":
        "Select the rent to settle.",
    "Un loyer annulé ne peut pas recevoir la caution.":
        "A cancelled rent cannot receive the security deposit.",
    "Une échéance annulée ne peut pas recevoir de paiement.":
        "A cancelled due item cannot receive a payment.",
    "La devise ne correspond pas à l'échéance.":
        "The currency does not match the due item.",
    "Cette échéance ne t'appartient pas.":
        "This due item does not belong to you.",
    "Le bien n'a pas de bailleur principal.":
        "The property has no primary landlord.",
    "Impossible de générer une référence unique.":
        "Unable to generate a unique reference.",
    "Cette échéance est introuvable.":
        "This due item could not be found.",
    "Une échéance annulée ne peut pas recevoir de demande.":
        "A cancelled due item cannot receive a request.",
    "Moyen de paiement invalide.": "Invalid payment method.",
    "Cette demande a déjà été traitée.":
        "This request has already been processed.",
    "Le montant reçu doit être strictement positif.":
        "The received amount must be strictly positive.",
    "Le motif est obligatoire.": "A reason is required.",
    "Tu ne peux pas annuler cette demande.":
        "You cannot cancel this request.",
    "Signature du webhook invalide.": "Invalid webhook signature.",
    "Appartement": "Apartment",
    "Terrain": "Land",
    "Local commercial": "Commercial premises",
    "bien": "property",
    "biens": "properties",
    "Ce compte possède déjà un rôle pour ce bien.":
        "This account already has a role for this property.",
    "IMMOLIB_SMS_MAX_CHARS doit etre positif.":
        "IMMOLIB_SMS_MAX_CHARS must be positive.",
    "SMS envoye": "SMS sent",
    "SMS envoyes": "SMS sent",
    "accuse de reception SMS": "SMS delivery receipt",
    "accuses de reception SMS": "SMS delivery receipts",
    "Reponse de token Orange illisible.":
        "Unreadable Orange token response.",
    "Orange n'a pas renvoye d'access_token.":
        "Orange did not return an access token.",
    "Reponse Orange illisible.": "Unreadable Orange response.",
    "Orange n'a pas renvoye de resource_id.":
        "Orange did not return a resource_id.",
    "Cette fonctionnalité est disponible avec le plan {plan}.":
        "This feature is available with the {plan} plan.",
    "Vous êtes déjà abonné à ce plan.":
        "You are already subscribed to this plan.",
    "Le paiement en ligne n’est pas configuré pour ce compte.":
        "Online payment is not configured for this account.",
    "Le plan Gratuit ne peut pas être annulé.":
        "The Free plan cannot be cancelled.",
    "Votre abonnement est déjà annulé.":
        "Your subscription is already cancelled.",
    "Le paiement en ligne est momentanément indisponible.":
        "Online payment is temporarily unavailable.",
    "Réservé aux administrateurs ImmoLib.":
        "Restricted to ImmoLib administrators.",
    "Texte": "Text",
    "Image": "Image",
    "Vidéo": "Video",
    "Audio": "Audio",
    "Document": "Document",
    "Sticker": "Sticker",
    "Localisation": "Location",
    "Contacts": "Contacts",
    "Bouton": "Button",
    "Interactif": "Interactive",
    "Inconnu": "Unknown",
    "message WhatsApp entrant": "incoming WhatsApp message",
    "messages WhatsApp entrants": "incoming WhatsApp messages",
    "Envoyé": "Sent",
    "Délivré": "Delivered",
    "Lu": "Read",
    "Échec": "Failed",
    "statut WhatsApp": "WhatsApp status",
    "statuts WhatsApp": "WhatsApp statuses",
}

po = polib.pofile(str(PO), encoding="utf-8")
missing = [e for e in po if not e.msgstr]
filled = 0
for entry in missing:
    translation = TRANSLATIONS.get(entry.msgid)
    if translation is None:
        continue
    entry.msgstr = translation
    filled += 1

still = [e.msgid for e in po if not e.msgstr]
po.save(str(PO))
print(f"filled: {filled} / {len(missing)} | restantes: {len(still)}")
for s in still:
    print("STILL:", s.replace("\n", "\\n")[:120])
