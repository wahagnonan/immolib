from rest_framework.pagination import PageNumberPagination


class LargeListPagination(PageNumberPagination):
    """Pagination systématique : toutes les listes sont bornées par défaut.

    Les anciens clients passaient par un tableau brut quand aucun paramètre
    ``page`` n'était fourni ; le frontend utilise désormais un dépaquetage
    explicite de l'enveloppe ``{count, next, previous, results}``.
    """

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100
