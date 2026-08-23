# coding: utf8
"""
Epuration (purge) de l'historique, portee depuis ramasse10_sql.py :
epuration() / after_date10() / valider_epur() / sortir_epur().

Supprime de la table `histo` toutes les lignes anterieures a une date
limite choisie par l'utilisateur (par defaut, aujourd'hui - 30 jours,
comme l'original). Comme dans l'original, cette suppression n'est PAS
filtree par type de ramasse (code_ram) : elle purge l'historique de TOUS
les types de ramasse a la fois - c'est le comportement exact de la requete
de depart (`delete from histo where date_ram < ...`, sans condition sur
code_ram).

Difference volontaire par rapport a l'original : l'original supprimait
directement au clic sur "Valider", sans annoncer au prealable combien de
lignes seraient touchees. Le portage affiche d'abord ce nombre (compter())
et demande une confirmation explicite avant d'executer epurer() - une
purge est irreversible et touche potentiellement tous les magasins/types
de ramasse a la fois, une confirmation minimale semblait justifiee.
"""
from datetime import date, timedelta


def date_limite_defaut(jours=30):
    """Date du jour moins `jours` jours, au format jj/mm/aaaa (= le calcul fait dans epuration())."""
    w = date.today() - timedelta(days=jours)
    return w.strftime("%d/%m/%Y")


def compter(conn, date_limite_amj):
    """Nombre de lignes de `histo` strictement anterieures a la date limite (format aaaa-mm-jj)."""
    cur = conn.cursor()
    cur.execute("select count(*) from histo where date_ram < %s", (date_limite_amj,))
    return cur.fetchone()[0] or 0


def epurer(conn, date_limite_amj):
    """
    Equivalent de valider_epur() : supprime definitivement toutes les
    lignes de `histo` anterieures a la date limite (format aaaa-mm-jj).
    Renvoie le nombre de lignes supprimees.
    """
    cur = conn.cursor()
    cur.execute("delete from histo where date_ram < %s", (date_limite_amj,))
    nb = cur.rowcount
    conn.commit()
    return nb
