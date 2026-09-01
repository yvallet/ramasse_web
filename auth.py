# coding: utf8
"""
Authentification (fonctionnalite absente de l'original, ajoutee pour
permettre un usage multi-site sur un serveur partage) :
  - /login, /logout
  - /mot-de-passe-oublie puis /reinitialiser-mot-de-passe/<token> : vrai
    flux par e-mail, avec un lien signe valable 1h (voir _generer_jeton/
    _lire_jeton ci-dessous et services/mail.py). Remplace l'ancienne
    version simplifiee (login + nouveau mot de passe sur le meme ecran,
    sans verification) qui permettait a quiconque connaissant l'adresse
    d'un compte de reinitialiser son mot de passe - inacceptable des lors
    que l'application est exposee sur Internet (voir DEPLOIEMENT_O2SWITCH.md).
  - Anti-force-brute en memoire (fenetre glissante par IP) sur /login et
    /mot-de-passe-oublie : voir _trop_de_tentatives/_noter_echec.
  - Un decorateur `login_required` (utilisable explicitement) et un hook
    global (`before_app_request`) qui protege TOUTES les routes de
    l'application par defaut, sauf celles de la liste blanche
    PUBLIC_ENDPOINTS ci-dessous - plus sur qu'un @login_required a poser
    sur chaque route une par une (impossible d'en oublier une).
  - `admin_required` : reserve les routes a CODE_BA = '00' (menu
    Utilisateurs, sauvegarde SQL complete - voir admin.py).
  - Un context_processor qui expose `current_user` et `est_admin` a tous
    les templates (menu, affichage "connecte en tant que...").
"""
import time
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    session, current_app,
)
from itsdangerous import URLSafeTimedSerializer, BadData, SignatureExpired

import db
from services import mail as sm
from services import utilisateurs as su

auth_bp = Blueprint("auth", __name__)

# Routes accessibles sans etre connecte. "static" est le nom d'endpoint
# Flask standard pour les fichiers de static/ (style.css, admin.js...).
PUBLIC_ENDPOINTS = {
    "auth.login", "auth.mot_de_passe_oublie", "auth.reinitialiser_mot_de_passe", "static",
}

DUREE_JETON_RESET = 3600  # 1h, comme annonce a l'utilisateur

# --------------------------------------------------------------------- #
# Anti-force-brute : fenetre glissante en memoire, par adresse IP. Fonctionne
# pour un seul process (le cas d'un hebergement mutualise type o2switch) ;
# l'etat est perdu a chaque redemarrage, ce qui est accepte (voir le plan de
# mise en production). Evolutif vers une table SQL si un jour plusieurs
# process doivent partager cet etat.
# --------------------------------------------------------------------- #
_TENTATIVES = {}  # {ip: [horodatage_echec, ...]}
MAX_TENTATIVES = 10
FENETRE_TENTATIVES = 15 * 60  # secondes


def _reset_tentatives():
    """Vide l'etat en memoire - reserve aux tests."""
    _TENTATIVES.clear()


def _purger(ip, maintenant):
    horodatages = [t for t in _TENTATIVES.get(ip, []) if maintenant - t < FENETRE_TENTATIVES]
    if horodatages:
        _TENTATIVES[ip] = horodatages
    else:
        _TENTATIVES.pop(ip, None)
    return horodatages


def _trop_de_tentatives(ip):
    return len(_purger(ip, time.time())) >= MAX_TENTATIVES


def _noter_echec(ip):
    maintenant = time.time()
    _purger(ip, maintenant)
    _TENTATIVES.setdefault(ip, []).append(maintenant)


def _oublier_tentatives(ip):
    _TENTATIVES.pop(ip, None)


def utilisateur_courant():
    """{'id', 'login', 'code_ba', 'nom_ba'} de l'utilisateur connecte, ou None."""
    return session.get("utilisateur")


def login_required(f):
    """
    Decorateur explicite (utile pour la lisibilite d'une route precise) -
    la protection reelle et systematique est assuree par le hook
    before_app_request ci-dessous, qui s'applique a toute l'application.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not utilisateur_courant():
            flash("Veuillez vous connecter.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    """Reserve une route au CODE_BA administrateur ('00')."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        utilisateur = utilisateur_courant()
        if not utilisateur:
            flash("Veuillez vous connecter.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        if not su.est_admin(utilisateur):
            flash("Cette page est reservee a l'administrateur.", "error")
            return redirect(url_for("saisie"))
        return f(*args, **kwargs)
    return wrapper


@auth_bp.before_app_request
def _exiger_connexion():
    """
    Protection globale : toute route non listee dans PUBLIC_ENDPOINTS
    exige une session utilisateur active. Applique a toute l'application
    (routes de app.py ET de admin.py), pas seulement a ce Blueprint.
    """
    if request.endpoint is None or request.endpoint in PUBLIC_ENDPOINTS:
        return
    if not utilisateur_courant():
        flash("Veuillez vous connecter.", "warning")
        return redirect(url_for("auth.login", next=request.path))


@auth_bp.app_context_processor
def _injecter_utilisateur_courant():
    utilisateur = utilisateur_courant()
    return {
        "current_user": utilisateur,
        "est_admin": su.est_admin(utilisateur) if utilisateur else False,
    }


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = request.remote_addr or "?"
        if _trop_de_tentatives(ip):
            flash("Trop de tentatives de connexion. Reessayez dans quelques minutes.", "error")
            current_app.logger.warning("Connexion bloquee (trop de tentatives) depuis %s", ip)
            return render_template("login.html", login=request.form.get("login", "")), 429

        login_saisi = (request.form.get("login") or "").strip()
        mot_de_passe = request.form.get("mot_de_passe") or ""

        conn = db.get_db()
        utilisateur = su.verifier_identifiants(conn, login_saisi, mot_de_passe)

        if utilisateur is None:
            _noter_echec(ip)
            flash("Login ou mot de passe incorrect.", "error")
            current_app.logger.warning("Echec de connexion pour le login : %s", login_saisi)
            return render_template("login.html", login=login_saisi)

        _oublier_tentatives(ip)
        session.clear()
        session["utilisateur"] = utilisateur
        current_app.logger.info(
            "Connexion : %s (CODE_BA %s - %s)", utilisateur["login"], utilisateur["code_ba"], utilisateur["nom_ba"]
        )

        suivant = request.args.get("next")
        if suivant and suivant.startswith("/") and not suivant.startswith("//"):
            return redirect(suivant)
        return redirect(url_for("saisie"))

    return render_template("login.html", login="")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    utilisateur = session.get("utilisateur")
    session.clear()
    if utilisateur:
        current_app.logger.info("Deconnexion : %s", utilisateur.get("login"))
    flash("Vous etes deconnecte.", "ok")
    return redirect(url_for("auth.login"))


def _serialiseur():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="reinit-mdp")


def _generer_jeton(login, fragment):
    return _serialiseur().dumps({"l": login, "f": fragment})


def _lire_jeton(token, max_age=DUREE_JETON_RESET):
    """Renvoie (login, fragment_hash) si le jeton est valide et non expire, sinon None."""
    try:
        charge = _serialiseur().loads(token, max_age=max_age)
    except (BadData, SignatureExpired):
        return None
    if not isinstance(charge, dict):
        return None
    return charge.get("l"), charge.get("f")


@auth_bp.route("/mot-de-passe-oublie", methods=["GET", "POST"])
def mot_de_passe_oublie():
    """
    Envoie, si le compte existe, un e-mail contenant un lien de
    reinitialisation valable 1h (voir _generer_jeton, services/mail.py). Le
    message affiche est volontairement le meme que le login existe ou non,
    pour ne pas laisser deviner l'existence d'un compte a partir de son
    adresse e-mail.
    """
    if request.method == "POST":
        ip = request.remote_addr or "?"
        if _trop_de_tentatives(ip):
            flash("Trop de demandes. Reessayez dans quelques minutes.", "error")
            return render_template("mot_de_passe_oublie.html", login=""), 429

        login_saisi = (request.form.get("login") or "").strip()
        # Chaque demande compte pour la limite, que le compte existe ou non :
        # sinon un compte existant pourrait etre spamme d'e-mails de
        # reinitialisation sans jamais declencher le blocage (seul le cas
        # "login inconnu" comptait auparavant).
        _noter_echec(ip)

        conn = db.get_db()
        utilisateur = su.trouver_par_login(conn, login_saisi)

        if utilisateur:
            fragment = su.fragment_hash(conn, login_saisi)
            token = _generer_jeton(utilisateur["login"], fragment)
            base = current_app.config.get("APP_BASE_URL")
            if base:
                lien = base.rstrip("/") + url_for("auth.reinitialiser_mot_de_passe", token=token)
            else:
                lien = url_for("auth.reinitialiser_mot_de_passe", token=token, _external=True)

            corps = (
                "Bonjour,\n\n"
                "Une reinitialisation de mot de passe a ete demandee pour ce compte "
                "(Ramasse journaliere - %s).\n\n"
                "Pour choisir un nouveau mot de passe, suivez ce lien (valable 1 heure) :\n%s\n\n"
                "Si vous n'etes pas a l'origine de cette demande, ignorez cet e-mail : "
                "votre mot de passe actuel reste valide.\n"
            ) % (utilisateur.get("nom_ba") or "", lien)

            try:
                sm.envoyer(
                    current_app.config, utilisateur["login"],
                    "Reinitialisation de votre mot de passe", corps,
                    logger=current_app.logger,
                )
            except RuntimeError as e:
                current_app.logger.error("Envoi de l'e-mail de reinitialisation echoue : %s", e)

        flash(
            "Si ce compte existe, un e-mail avec un lien de reinitialisation vient de lui etre envoye.",
            "ok",
        )
        return redirect(url_for("auth.login"))

    return render_template("mot_de_passe_oublie.html", login="")


@auth_bp.route("/reinitialiser-mot-de-passe/<token>", methods=["GET", "POST"])
def reinitialiser_mot_de_passe(token):
    conn = db.get_db()
    resultat = _lire_jeton(token)
    if resultat is None:
        flash("Ce lien de reinitialisation est invalide ou a expire. Refaites une demande.", "error")
        return redirect(url_for("auth.mot_de_passe_oublie"))

    login_jeton, fragment_jeton = resultat
    if su.fragment_hash(conn, login_jeton) != fragment_jeton:
        # Le mot de passe a change depuis l'emission du lien (ou compte supprime).
        flash("Ce lien de reinitialisation n'est plus valable. Refaites une demande.", "error")
        return redirect(url_for("auth.mot_de_passe_oublie"))

    if request.method == "POST":
        nouveau = request.form.get("nouveau_mot_de_passe") or ""
        confirmation = request.form.get("confirmation") or ""

        if nouveau != confirmation:
            flash("Les deux mots de passe saisis ne sont pas identiques.", "error")
            return render_template("reinitialiser_mot_de_passe.html", token=token)

        if len(nouveau) < su.LONGUEUR_MIN_MOT_DE_PASSE:
            flash("Le mot de passe doit faire au moins %s caracteres." % su.LONGUEUR_MIN_MOT_DE_PASSE, "error")
            return render_template("reinitialiser_mot_de_passe.html", token=token)

        su.changer_mot_de_passe(conn, login_jeton, nouveau)
        session.clear()
        current_app.logger.info("Mot de passe reinitialise via lien e-mail pour : %s", login_jeton)
        flash("Mot de passe mis a jour. Vous pouvez maintenant vous connecter.", "ok")
        return redirect(url_for("auth.login"))

    return render_template("reinitialiser_mot_de_passe.html", token=token)
