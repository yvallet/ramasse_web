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

Differences volontaires par rapport a l'original :
- L'ecran affiche d'abord le nombre de lignes concernees (compter()) et
  demande une confirmation explicite avant d'executer epurer() - une
  purge est irreversible, une confirmation minimale semblait justifiee.
- Cloisonnement multi-site (CODE_BA) : fonctionnalite absente de
  l'original. La purge reste desormais TOUJOURS limitee au site
  (code_ba) de l'utilisateur connecte (voir auth.py) - un utilisateur ne
  peut epurer que l'historique de son propre site, jamais celui d'un
  autre. Il n'y a pas de mode "tous les sites a la fois", y compris pour
  l'administrateur (CODE_BA='00'), qui n'a de toute facon pas de donnees
  de ramasse propres.
"""
from datetime import date, timedelta


def date_limite_defaut(jours=30):
    """Date du jour moins `jours` jours, au format jj/mm/aaaa (= le calcul fait dans epuration())."""
    w = date.today() - timedelta(days=jours)
    return w.strftime("%d/%m/%Y")


def compter(conn, code_ba, date_limite_amj):
    """Nombre de lignes de `histo` du site `code_ba`, strictement anterieures a la date limite (format aaaa-mm-jj)."""
    cur = conn.cursor()
    cur.execute("select count(*) from histo where code_ba = %s and date_ram < %s", (code_ba, date_limite_amj))
    return cur.fetchone()[0] or 0


def epurer(conn, code_ba, date_limite_amj):
    """
    Equivalent de valider_epur() : supprime definitivement toutes les
    lignes de `histo` du site `code_ba` anterieures a la date limite
    (format aaaa-mm-jj). Renvoie le nombre de lignes supprimees.
    """
    cur = conn.cursor()
    cur.execute("delete from histo where code_ba = %s and date_ram < %s", (code_ba, date_limite_amj))
    nb = cur.rowcount
    conn.commit()
    return nb
