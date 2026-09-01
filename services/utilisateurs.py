# coding: utf8
"""
Gestion des comptes utilisateur (table `user`), fonctionnalite absente de
l'original : ramasse10_sql.py ne demandait aucune authentification (usage
desktop local). Ajoutee pour permettre un usage multi-site sur un serveur
partage : chaque compte est rattache a un CODE_BA (le site), qui remplace
desormais le CODE_BA jusque-la fixe dans le .env (voir config.py).

Convention : CODE_BA = '00' identifie l'administrateur technique, seul
autorise a gerer les comptes (menu "Utilisateurs"). Un administrateur n'a
pas de donnees de ramasse propres (pas d'ecran de saisie pour lui) ; son
role se limite a la maintenance des comptes et, au besoin, du referentiel
partage (magasins/fournisseurs/articles/types) et de la sauvegarde SQL
complete de la base.

Le mot de passe n'est jamais stocke en clair : la colonne `mot_de_passe`
contient un hash (werkzeug.security, deja fourni avec Flask - aucune
dependance supplementaire).
"""
import re

from werkzeug.security import generate_password_hash, check_password_hash

CODE_ADMIN = "00"
LONGUEUR_MIN_MOT_DE_PASSE = 4

_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_COLONNES = ["id", "login", "code_ba", "nom_ba"]  # sans mot_de_passe : jamais renvoye au navigateur


def valider_email(login):
    """Le login doit etre une adresse mail (controle simple, pas de verification DNS/MX)."""
    return bool(login) and bool(_RE_EMAIL.match(login.strip()))


def est_admin(utilisateur):
    """Convention : CODE_BA = '00' = administrateur (seul a acceder au menu Utilisateurs)."""
    return bool(utilisateur) and str(utilisateur.get("code_ba")) == CODE_ADMIN


def _normaliser_login(login):
    return (login or "").strip().lower()


def trouver_par_login(conn, login):
    """Renvoie {id, login, code_ba, nom_ba} (sans mot_de_passe) ou None."""
    cur = conn.cursor()
    cur.execute(
        "select id, login, code_ba, nom_ba from `user` where login = %s",
        (_normaliser_login(login),),
    )
    row = cur.fetchone()
    return dict(zip(_COLONNES, row)) if row else None


def verifier_identifiants(conn, login, mot_de_passe):
    """
    Equivalent d'un controle de connexion classique : renvoie l'utilisateur
    {id, login, code_ba, nom_ba} si login+mot de passe sont corrects, sinon
    None (login inconnu ou mot de passe errone - meme reponse dans les deux
    cas, pour ne pas laisser deviner si un compte existe).
    """
    cur = conn.cursor()
    cur.execute(
        "select id, login, mot_de_passe, code_ba, nom_ba from `user` where login = %s",
        (_normaliser_login(login),),
    )
    row = cur.fetchone()
    if not row:
        return None
    id_, login_bd, hash_stocke, code_ba, nom_ba = row
    if not check_password_hash(hash_stocke, mot_de_passe or ""):
        return None
    return {"id": id_, "login": login_bd, "code_ba": code_ba, "nom_ba": nom_ba}


def lister(conn):
    """Tous les comptes (sans mot_de_passe), tries par CODE_BA puis login."""
    cur = conn.cursor()
    cur.execute("select id, login, code_ba, nom_ba from `user` order by code_ba, login")
    return [dict(zip(_COLONNES, row)) for row in cur.fetchall()]


def creer(conn, login, mot_de_passe, code_ba, nom_ba):
    """Cree un compte. Leve ValueError si une donnee est invalide ou si le login existe deja."""
    login = _normaliser_login(login)
    code_ba = (code_ba or "").strip()
    nom_ba = (nom_ba or "").strip()

    if not valider_email(login):
        raise ValueError("Le login doit etre une adresse mail valide.")
    if not mot_de_passe or len(mot_de_passe) < LONGUEUR_MIN_MOT_DE_PASSE:
        raise ValueError("Le mot de passe doit faire au moins %s caracteres." % LONGUEUR_MIN_MOT_DE_PASSE)
    if not code_ba:
        raise ValueError("Il faut indiquer le CODE_BA.")
    if not nom_ba:
        raise ValueError("Il faut indiquer le nom du BA (nom_ba).")
    if trouver_par_login(conn, login):
        raise ValueError("Ce login existe deja.")

    cur = conn.cursor()
    cur.execute(
        "insert into `user` (id, login, mot_de_passe, code_ba, nom_ba) values (%s, %s, %s, %s, %s)",
        (0, login, generate_password_hash(mot_de_passe), code_ba, nom_ba),
    )
    conn.commit()


def modifier(conn, login, code_ba, nom_ba):
    """Met a jour le CODE_BA/nom_ba d'un compte existant (pas le mot de passe, voir changer_mot_de_passe)."""
    login = _normaliser_login(login)
    code_ba = (code_ba or "").strip()
    nom_ba = (nom_ba or "").strip()

    if not code_ba:
        raise ValueError("Il faut indiquer le CODE_BA.")
    if not nom_ba:
        raise ValueError("Il faut indiquer le nom du BA (nom_ba).")
    if not trouver_par_login(conn, login):
        raise ValueError("Ce compte n'existe pas.")

    cur = conn.cursor()
    cur.execute(
        "update `user` set code_ba = %s, nom_ba = %s where login = %s",
        (code_ba, nom_ba, login),
    )
    conn.commit()


def changer_mot_de_passe(conn, login, nouveau_mot_de_passe):
    """
    Equivalent de la reinitialisation de mot de passe (menu Utilisateurs,
    ou "mot de passe oublie" - voir auth.py). Leve ValueError si le compte
    n'existe pas ou si le nouveau mot de passe est trop court.
    """
    login = _normaliser_login(login)
    if not nouveau_mot_de_passe or len(nouveau_mot_de_passe) < LONGUEUR_MIN_MOT_DE_PASSE:
        raise ValueError("Le mot de passe doit faire au moins %s caracteres." % LONGUEUR_MIN_MOT_DE_PASSE)
    if not trouver_par_login(conn, login):
        raise ValueError("Ce compte n'existe pas.")

    cur = conn.cursor()
    cur.execute(
        "update `user` set mot_de_passe = %s where login = %s",
        (generate_password_hash(nouveau_mot_de_passe), login),
    )
    conn.commit()


def supprimer(conn, login):
    """
    Supprime un compte. Leve ValueError s'il n'existe pas, ou si c'est le
    DERNIER compte administrateur (CODE_BA='00') restant - pour ne jamais
    se retrouver sans personne capable de gerer les comptes.
    """
    login = _normaliser_login(login)
    utilisateur = trouver_par_login(conn, login)
    if not utilisateur:
        raise ValueError("Ce compte n'existe pas.")

    if est_admin(utilisateur):
        cur = conn.cursor()
        cur.execute("select count(*) from `user` where code_ba = %s", (CODE_ADMIN,))
        if (cur.fetchone()[0] or 0) <= 1:
            raise ValueError("Impossible de supprimer le dernier compte administrateur.")

    cur = conn.cursor()
    cur.execute("delete from `user` where login = %s", (login,))
    conn.commit()


def assurer_admin_par_defaut(conn, mot_de_passe=None):
    """
    Cree le compte administrateur par defaut (yvmaison@free.fr / CODE_BA='00'
    / nom_ba='Administrateur') s'il n'existe pas encore. `mot_de_passe` est
    "admin" si non fourni (comportement historique, utilise en local) ; en
    production, app.py fournit explicitement ADMIN_INITIAL_PASSWORD (et
    n'appelle meme pas cette fonction si cette variable est absente).
    Appelee au demarrage de l'application (voir app.py). Idempotente : ne
    fait rien si le compte existe deja. Si la table `user` n'existe pas
    encore (migration SQL pas encore executee), l'appelant doit intercepter
    l'exception et continuer sans bloquer le demarrage - voir app.py.
    """
    if trouver_par_login(conn, "yvmaison@free.fr"):
        return False
    cur = conn.cursor()
    cur.execute(
        "insert into `user` (id, login, mot_de_passe, code_ba, nom_ba) values (%s, %s, %s, %s, %s)",
        (0, "yvmaison@free.fr", generate_password_hash(mot_de_passe or "admin"), CODE_ADMIN, "Administrateur"),
    )
    conn.commit()
    return True


def fragment_hash(conn, login):
    """
    Derniers caracteres du hash de mot de passe stocke pour `login` (ou None
    si le compte n'existe pas). Utilise pour lier un jeton de
    reinitialisation de mot de passe (voir auth.py) au mot de passe courant :
    des que le mot de passe change, le hash change, et tout jeton emis avant
    devient invalide - sans avoir besoin d'une table dediee aux jetons.
    """
    login = _normaliser_login(login)
    cur = conn.cursor()
    cur.execute("select mot_de_passe from `user` where login = %s", (login,))
    row = cur.fetchone()
    return row[0][-12:] if row else None
