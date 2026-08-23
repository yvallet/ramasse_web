# coding: utf8
"""
Fonctions de dates reprises de outils.py (module partage utilise par le
programme tkinter d'origine, via `from outils import *`).

Seules les fonctions reellement utilisees par ramasse10_sql.py ont ete
portees ici : date_jour, amj, jma, verif_date. Le reste de outils.py
(FTP/SFTP, etiquettes, PDF bon de reception...) ne concerne pas l'ecran de
saisie journaliere et n'a pas ete repris dans ce MVP.
"""
from datetime import date, datetime


def date_jour():
    """Date du jour au format jj/mm/aaaa (identique a outils.date_jour)."""
    w = str(date.today())
    return w[8:10] + "/" + w[5:7] + "/" + w[0:4]


def amj(wdt):
    """jj/mm/aaaa -> aaaa-mm-jj (pour les requetes SQL)."""
    if not wdt or len(wdt) == 0:
        return " "
    jj = wdt[0:2]
    mm = wdt[3:5]
    aa = wdt[6:11]
    return aa + "-" + mm + "-" + jj


def jma(wdt):
    """aaaa-mm-jj -> jj/mm/aaaa (pour l'affichage)."""
    if not wdt or len(wdt) < 6:
        return " "
    jj = wdt[8:11]
    mm = wdt[5:7]
    aa = wdt[0:4]
    return jj + "/" + mm + "/" + aa


def verif_date(wdt):
    """
    Controle et normalise une date saisie au format jj/mm/aaaa (ou variantes
    compactes jjmmaa, jjmmaaaa, jjmm). Reprise fidele de outils.verif_date.

    Retourne (statut, date_objet_ou_None, "jj/mm/aaaa"|None)
    statut = "OK" ou "KO"
    """
    auj = date.today()
    auj_aa = str(auj)[0:4]

    if not wdt:
        return "KO", auj, wdt

    if len(wdt) not in (10, 8, 6, 4):
        return "KO", auj, wdt

    if len(wdt) == 4:
        jj = wdt[0:2]
        mm = wdt[2:4]
        aa = auj_aa
        wdt = jj + "/" + mm + "/" + str(aa)

    if len(wdt) == 6:
        try:
            int(wdt)
        except ValueError:
            return "KO", None, None
        jj = wdt[0:2]
        mm = wdt[2:4]
        aa = wdt[4:7]
        yy = (1900 if aa > "30" else 2000) + int(aa)
        wdt = jj + "/" + mm + "/" + str(yy)

    if len(wdt) == 10:
        jj = wdt[0:2]
        mm = wdt[3:5]
        aa = wdt[6:11]

    if len(wdt) == 8:
        if wdt[2:3] == "/":
            jj = wdt[0:2]
            mm = wdt[3:5]
            aa = wdt[6:8]
            try:
                int(aa)
            except ValueError:
                return "KO", None, None
            yy = (1900 if aa > "30" else 2000) + int(aa)
            aa = str(yy)
        else:
            jj = wdt[0:2]
            mm = wdt[2:4]
            aa = wdt[4:9]

    if jj < "01" or jj > "31":
        return "KO", auj, wdt
    if mm < "01" or mm > "12":
        return "KO", auj, wdt
    if aa < "1900" or aa > "2099":
        return "KO", auj, wdt

    try:
        date_saisie = date(int(aa), int(mm), int(jj))
        wdt = jj + "/" + mm + "/" + aa
        return "OK", date_saisie, wdt
    except ValueError:
        return "KO", auj, wdt


NOMS_JOUR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def nom_jour(weekday):
    """weekday: 0=Lundi ... 6=Dimanche (comme datetime.weekday())."""
    return NOMS_JOUR[weekday]
