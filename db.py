# coding: utf8
"""
Couche d'acces a MySQL.

Contrairement au programme tkinter d'origine, qui ouvrait UNE SEULE
connexion globale au demarrage et la reutilisait pour tout le monde,
une application web doit ouvrir une connexion par requete HTTP : plusieurs
utilisateurs (plusieurs magasins/postes) peuvent travailler en meme temps,
et une connexion mysql.connector n'est pas thread-safe.

get_db() ouvre donc une connexion a la demande et la stocke dans le
contexte de la requete Flask (flask.g) ; elle est refermee automatiquement
a la fin de la requete par close_db(), enregistree via teardown_appcontext.
"""
import mysql.connector
from flask import g, current_app


def get_db():
    if "db" not in g:
        g.db = mysql.connector.connect(
            host=current_app.config["MYSQL_HOST"],
            port=current_app.config["MYSQL_PORT"],
            user=current_app.config["MYSQL_USER"],
            password=current_app.config["MYSQL_PASSWORD"],
            database=current_app.config["MYSQL_DB"],
        )
    return g.db


def close_db(e=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app):
    app.teardown_appcontext(close_db)
