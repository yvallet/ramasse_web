# coding: utf8
"""
Petit adaptateur utilise UNIQUEMENT par les tests : il permet de faire
tourner les memes requetes SQL (ecrites avec des %s, style
mysql.connector) sur une base sqlite3 en memoire, pour verifier la
logique metier sans avoir besoin d'un vrai serveur MySQL.

Ne pas utiliser en production : le vrai code applicatif (db.py) se
connecte a MySQL avec mysql.connector.
"""
import sqlite3


class ShimCursor:
    def __init__(self, cur):
        self._cur = cur

    def execute(self, sql, params=None):
        sql2 = sql.replace("%s", "?")

        # MySQL (sans le mode strict NO_AUTO_VALUE_ON_ZERO actif sur la
        # connexion applicative) traite un id=0 insere sur une colonne
        # AUTO_INCREMENT comme "generer une nouvelle valeur", exactement
        # comme NULL. Le code applicatif (services/ramasse.py, copie de
        # creer_histo) insere volontairement id=0 pour reproduire ce
        # comportement. sqlite ne fait pas cette conversion automatiquement
        # pour un INTEGER PRIMARY KEY AUTOINCREMENT : on l'emule ici, dans
        # le shim de test uniquement.
        if params and "insert into histo" in sql2.lower() and params[0] == 0:
            params = (None,) + tuple(params[1:])

        if params is None:
            self._cur.execute(sql2)
        else:
            self._cur.execute(sql2, params)
        return self

    def fetchall(self):
        return self._cur.fetchall()

    def fetchone(self):
        return self._cur.fetchone()

    @property
    def rowcount(self):
        # Utilise par services/epuration.py (nombre de lignes supprimees),
        # comme cur.rowcount avec mysql.connector dans l'original.
        return self._cur.rowcount


class ShimConnection:
    def __init__(self, real_conn):
        self._conn = real_conn

    def cursor(self):
        return ShimCursor(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


SCHEMA = """
create table histo (
  id integer primary key autoincrement,
  code_ram text, date_ram text, magasin integer, nom text, codfour text,
  nolig integer, codart text, libart text, qte real, rebut real, depot text
);
create table modeles (
  id integer primary key autoincrement,
  code_ram text, magasin integer, nom text,
  lundi integer, mardi integer, mercredi integer, jeudi integer, vendredi integer,
  codfour text, nolig integer, codart text, libart text, depot text, partenaire text,
  samedi integer, rebut text
);
create table param (
  id integer primary key autoincrement,
  code_type text, code text, libelle text
);
"""


def build_test_db():
    raw = sqlite3.connect(":memory:")
    raw.executescript(SCHEMA)

    # -- type de ramasse --
    raw.execute("insert into param (code_type, code, libelle) values ('T','BA','Ramasse BA')")

    # -- fournisseurs et articles references par les modeles ci-dessous --
    for code, libelle in [("02580004", "Leclerc Drive"), ("02580038", "Intermarche Sauvigny")]:
        raw.execute("insert into param (code_type, code, libelle) values ('F', ?, ?)", (code, libelle))
    for code, libelle in [
        ("0119000", "Pain - Viennoiserie"), ("4520000", "Fruits-Legumes Non Transformes"),
        ("4620001", "Viande - Poisson"), ("4320001", "Produits Laitiers"),
    ]:
        raw.execute("insert into param (code_type, code, libelle) values ('A', ?, ?)", (code, libelle))

    # -- modele magasin 10 : ouvert lundi, 3 lignes, ferme le mardi --
    for nolig, codart, libart in [(1, "0119000", "Pain"), (2, "4520000", "Fruits-Legumes"), (3, "4620001", "Viande")]:
        raw.execute(
            """insert into modeles
               (code_ram, magasin, nom, lundi, mardi, mercredi, jeudi, vendredi,
                codfour, nolig, codart, libart, depot, partenaire, samedi, rebut)
               values ('BA', 10, 'Magasin Dix', 1, 1, 1, 1, 1, '02580004', ?, ?, ?, '03', '', 0, 'O')""",
            (nolig, codart, libart),
        )

    # -- modele magasin 20 : ferme le lundi, ouvert le mardi, 2 lignes --
    for nolig, codart, libart in [(1, "0119000", "Pain"), (2, "4320001", "Produits Laitiers")]:
        raw.execute(
            """insert into modeles
               (code_ram, magasin, nom, lundi, mardi, mercredi, jeudi, vendredi,
                codfour, nolig, codart, libart, depot, partenaire, samedi, rebut)
               values ('BA', 20, 'Magasin Vingt', 0, 1, 1, 1, 1, '02580038', ?, ?, ?, '03', '', 0, 'O')""",
            (nolig, codart, libart),
        )

    raw.commit()
    return ShimConnection(raw)
