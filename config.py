# coding: utf8
"""
Configuration de l'application, lue depuis des variables d'environnement
(voir .env.example -> copier en .env et adapter).

Reprend les memes parametres que l'ancien param_ramasse.txt :
  - connexion MySQL (serveur, base, user, password)
  - repertoire d'export des CSV (VIF)

IMPORTANT securite : l'ancien fichier param_ramasse.txt contenait le mot de
passe MySQL en clair dans un fichier texte a cote du programme. Ici, aucune
valeur sensible n'a de defaut en dur dans le code (voir RAMASSE_ENV
ci-dessous) : tout doit venir d'un fichier .env (non commite, voir
.env.example) ou de variables d'environnement systeme.

CODE_BA : il n'y a plus de CODE_BA fixe ici (fonctionnalite absente de
l'original). Chaque utilisateur est desormais rattache a un CODE_BA via son
compte (table `user`, voir services/utilisateurs.py et auth.py) - c'est ce
CODE_BA, lie a la connexion, qui determine les magasins/l'historique
visibles, jamais une valeur de configuration globale au serveur.

RAMASSE_ENV : "local" (defaut, usage reseau local/poste de developpement) ou
"production" (serveur expose sur Internet, ex. o2switch). Pilote le mode
debug de Flask, les attributs de securite des cookies de session, le
fail-fast sur les secrets par defaut, et si l'appli se considere derriere un
proxy HTTPS (Apache/Passenger) - voir _assurer_configuration_prod() dans
app.py et DEPLOIEMENT_O2SWITCH.md.
"""
import os
from datetime import timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv n'est pas installe : on continue avec les seules
    # variables d'environnement deja presentes dans le systeme.
    pass


def _bool(valeur, defaut=False):
    if valeur is None:
        return defaut
    return str(valeur).strip().lower() in ("1", "true", "vrai", "oui", "yes", "on")


class Config:
    RAMASSE_ENV = os.environ.get("RAMASSE_ENV", "local").strip().lower()
    IS_PROD = RAMASSE_ENV == "production"

    DEBUG = not IS_PROD

    # Cle par defaut volontairement non secrete et explicitement nommee : ne
    # sert qu'a demarrer en local sans .env. En production, une valeur par
    # defaut ou vide fait echouer le demarrage (voir app.py, fail-fast).
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-key-not-for-production")

    MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
    MYSQL_DB = os.environ.get("MYSQL_DB", "yvallet_base")
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")

    # Repertoire ou sont ecrits les CSV d'export (import VIF), et les
    # sauvegardes SQL completes (equivalent Repertoire_csv de
    # param_ramasse.txt). Plus de CODE_BA ici : voir la note en tete de
    # fichier.
    CSV_EXPORT_DIR = os.environ.get("CSV_EXPORT_DIR", os.path.join(os.getcwd(), "export_csv"))

    # Sauvegarde SQL complete de la base (fonctionnalite absente de
    # l'original, voir services/sauvegarde.py) : chemin de l'executable
    # mysqldump, si different de celui trouve automatiquement dans le PATH
    # systeme (utile notamment sous Windows).
    MYSQLDUMP_PATH = os.environ.get("MYSQLDUMP_PATH", "mysqldump")

    # Compte administrateur par defaut (voir services/utilisateurs.py,
    # assurer_admin_par_defaut) : en local, "admin" est utilise si absent
    # (comportement historique). En production, aucun compte n'est cree tant
    # que cette variable n'est pas definie - voir app.py.
    ADMIN_INITIAL_PASSWORD = os.environ.get("ADMIN_INITIAL_PASSWORD") or None

    # --- Cookies de session ------------------------------------------- #
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = IS_PROD
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    SESSION_REFRESH_EACH_REQUEST = True

    PREFERRED_URL_SCHEME = "https" if IS_PROD else "http"

    # Taille max d'une requete (formulaires) : protection simple contre les
    # requetes anormalement volumineuses.
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024

    # Derriere un reverse proxy (Apache + Passenger sur o2switch) : active
    # ProxyFix (voir app.py) pour que Flask voie la vraie IP client et le
    # schema HTTPS d'origine. Actif par defaut en production, desactivable
    # au besoin (BEHIND_PROXY=0).
    BEHIND_PROXY = _bool(os.environ.get("BEHIND_PROXY"), defaut=IS_PROD)

    # --- Envoi d'e-mail (reinitialisation de mot de passe, voir auth.py) #
    # Si SMTP_HOST est absent, aucun e-mail n'est envoye : le lien de
    # reinitialisation est simplement journalise (logs/app.log), pratique
    # en local sans serveur SMTP a configurer.
    SMTP_HOST = os.environ.get("SMTP_HOST") or None
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER") or None
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD") or None
    SMTP_FROM = os.environ.get("SMTP_FROM") or SMTP_USER
    SMTP_STARTTLS = _bool(os.environ.get("SMTP_STARTTLS"), defaut=True)

    # Force le domaine utilise dans les liens envoyes par e-mail (utile
    # derriere un proxy/nom d'hote different de celui vu par Flask). Sans
    # cette variable, l'URL est construite a partir de la requete en cours.
    APP_BASE_URL = os.environ.get("APP_BASE_URL") or None
