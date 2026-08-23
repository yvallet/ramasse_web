# coding: utf8
"""
Configuration de l'application, lue depuis des variables d'environnement
(voir .env.example -> copier en .env et adapter).

Reprend les memes parametres que l'ancien param_ramasse.txt :
  - connexion MySQL (serveur, base, user, password)
  - repertoire d'export des CSV (VIF)
  - code BA

IMPORTANT securite : l'ancien fichier param_ramasse.txt contenait le mot de
passe MySQL en clair dans un fichier texte a cote du programme. Ici les
valeurs par defaut ci-dessous reprennent celles observees dans
param_ramasse.txt pour ne rien casser au demarrage, mais il est fortement
conseille de les redefinir via un fichier .env (non commite) plutot que de
les laisser en dur.
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv n'est pas installe : on continue avec les seules
    # variables d'environnement deja presentes dans le systeme.
    pass


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-moi-en-production")

    MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
    MYSQL_DB = os.environ.get("MYSQL_DB", "yvallet_base")
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "saanar")

    # Repertoire ou sont ecrits les CSV d'export (import VIF), et code BA
    # (equivalent Repertoire_csv / code_BA de param_ramasse.txt)
    CSV_EXPORT_DIR = os.environ.get("CSV_EXPORT_DIR", os.path.join(os.getcwd(), "export_csv"))
    CODE_BA = os.environ.get("CODE_BA", "58")

    # Sauvegarde SQL complete de la base (fonctionnalite absente de
    # l'original, voir services/sauvegarde.py) : chemin de l'executable
    # mysqldump, si different de celui trouve automatiquement dans le PATH
    # systeme (utile notamment sous Windows).
    MYSQLDUMP_PATH = os.environ.get("MYSQLDUMP_PATH", "mysqldump")
