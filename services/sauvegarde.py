# coding: utf8
"""
Sauvegarde complete de la base MySQL au format SQL, via `mysqldump`.

Fonctionnalite absente de l'original : ramasse10_sql.py ne contient aucune
sauvegarde automatisee de la base (seul l'export CSV VIF existe, qui ne
concerne que les lignes de la journee, pas la base entiere). Ajoutee a la
demande : genere un dump complet (structure + donnees, toutes les tables)
avec l'utilitaire `mysqldump`, enregistre dans le meme repertoire que les
exports CSV (CSV_EXPORT_DIR), sous le nom `sauvegarde-jjmmaaaa_hhmm.sql`.
"""
import os
import subprocess
from datetime import datetime

PREFIXE = "sauvegarde-"
SUFFIXE = ".sql"


def nom_fichier(horodatage=None):
    """
    Nom de fichier au format sauvegarde-jjmmaaaa_hhmm.sql.
    `horodatage` (datetime) est injectable pour les tests ; par defaut,
    l'instant present.
    """
    horodatage = horodatage or datetime.now()
    return PREFIXE + horodatage.strftime("%d%m%Y_%H%M") + SUFFIXE


def lister(repertoire):
    """
    Sauvegardes deja presentes dans `repertoire`, les plus recentes en
    premier : [{"nom":..., "taille":..., "date":...}, ...].
    """
    if not os.path.isdir(repertoire):
        return []
    entrees = []
    for nom in os.listdir(repertoire):
        if nom.startswith(PREFIXE) and nom.endswith(SUFFIXE):
            chemin = os.path.join(repertoire, nom)
            infos = os.stat(chemin)
            entrees.append({
                "nom": nom,
                "taille": infos.st_size,
                "date": datetime.fromtimestamp(infos.st_mtime),
            })
    entrees.sort(key=lambda e: e["date"], reverse=True)
    return entrees


def creer(config, repertoire, executer=subprocess.run, horodatage=None):
    """
    Lance mysqldump sur la base configuree et ecrit le resultat dans
    `repertoire`/sauvegarde-jjmmaaaa_hhmm.sql.

    `config` : mapping donnant acces a MYSQL_HOST/MYSQL_PORT/MYSQL_USER/
    MYSQL_PASSWORD/MYSQL_DB (app.config convient tel quel) et
    optionnellement MYSQLDUMP_PATH (chemin de l'executable, "mysqldump"
    par defaut si absent du PATH systeme).

    `executer` : injectable pour les tests, meme signature que
    subprocess.run (recoit stdout=<fichier ouvert>, stderr=subprocess.PIPE,
    env=...) et doit renvoyer un objet avec .returncode et .stderr.

    Leve RuntimeError si mysqldump est introuvable ou echoue (le fichier
    partiel est alors supprime). Renvoie le chemin complet du fichier cree.
    """
    os.makedirs(repertoire, exist_ok=True)
    chemin = os.path.join(repertoire, nom_fichier(horodatage))

    commande = [
        config.get("MYSQLDUMP_PATH") or "mysqldump",
        "-h", str(config["MYSQL_HOST"]),
        "-P", str(config["MYSQL_PORT"]),
        "-u", str(config["MYSQL_USER"]),
        "--routines", "--events", "--single-transaction",
        config["MYSQL_DB"],
    ]
    # Mot de passe transmis par variable d'environnement (MYSQL_PWD),
    # jamais sur la ligne de commande, pour ne pas l'exposer dans la liste
    # des processus du systeme (`ps`, gestionnaire des taches...).
    env = dict(os.environ)
    if config.get("MYSQL_PASSWORD"):
        env["MYSQL_PWD"] = config["MYSQL_PASSWORD"]

    try:
        with open(chemin, "wb") as sortie:
            resultat = executer(commande, stdout=sortie, stderr=subprocess.PIPE, env=env)
    except FileNotFoundError:
        _nettoyer(chemin)
        raise RuntimeError(
            "mysqldump est introuvable. Verifiez qu'il est installe et accessible "
            "(ou renseignez MYSQLDUMP_PATH dans .env)."
        )

    if resultat.returncode != 0:
        _nettoyer(chemin)
        erreur = resultat.stderr
        if isinstance(erreur, bytes):
            erreur = erreur.decode("utf-8", errors="replace")
        raise RuntimeError(
            "mysqldump a echoue : %s" % (erreur.strip() if erreur else "code retour %s" % resultat.returncode)
        )

    if os.path.getsize(chemin) == 0:
        _nettoyer(chemin)
        raise RuntimeError("mysqldump n'a produit aucune donnee (fichier vide).")

    return chemin


def _nettoyer(chemin):
    """Supprime un fichier de sauvegarde partiel/vide en cas d'echec."""
    try:
        if os.path.exists(chemin):
            os.remove(chemin)
    except OSError:
        pass
