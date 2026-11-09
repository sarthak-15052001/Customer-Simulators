from django.db import models


class Region(models.TextChoices):
    BRETAGNE_NORMANDIE = "Bretagne / Normandie"
    AQUITAINE_LANDES = "Aquitaine / Landes"
    MEDITERRANEE_PACA = "Méditerranée / PACA"
    ALPES_SAVOIE = "Alpes / Savoie"
    ALPES_DU_SUD = "Alpes du Sud"
    MASSIF_CENTRAL_JURA = "Massif Central / Jura"
    CAMPAGNE_PROVENCE = "Campagne / Provence"
    OCCITANIE_PYRENEES = "Occitanie / Pyrénées"


class Saison(models.TextChoices):
    HS = "hs", "Hors saison"
    VS = "vs", "Vacances scolaires"
    ETE = "ete", "Été"
    FETES = "fetes", "Fêtes"


class Formule(models.TextChoices):
    PC = "PC", "Pension complète"
    DP = "DP", "Demi-pension"
    LOC = "LOC", "Location"


class EnvCode(models.TextChoices):
    SEA = "sea", "Bord de mer"
    MOUNTAIN = "mountain", "Montagne"
    FOREST = "forest", "Nature/forêt"
    COUNTRYSIDE = "countryside", "Campagne"
    SUN = "sun", "Soleil/Méditerranée"