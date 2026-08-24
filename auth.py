# coding: utf8
"""
Authentification (fonctionnalite absente de l'original, ajoutee pour
permettre un usage multi-site sur un serveur partage) :
  - /login, /logout
  - /mot-de-passe-oublie : version SIMPLIFIEE SANS ENVOI D'EMAIL, choisie
    deliberement (pas de serveur SMTP a configurer) : l'utilisateur saisit
    son login et peut aussitot definir un nouveau mot de passe, sans lien
    de verification envoye par email. C'est moins sur qu'un vrai flux par
    email (n'importe qui connaissant l'adresse d'un utilisateur peut
    reinitialiser son mot de passe), a garder en tete si l'appli devient
    accessible publiquement - un vrai envoi d'email pourra etre ajoute
    plus tard sans tout reecrire (seule cette route serait a changer).
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
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    session, current_app,
)

import db
from services import utilisateurs as su

auth_bp = Blueprint("auth", __name__)

# Routes accessibles sans etre connecte. "static" est le nom d'endpoint
# Flask standard pour les fichiers de static/ (style.css, admin.js...).
PUBLIC_ENDPOINTS = {"auth.login", "auth.mot_de_passe_oublie", "static"}


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
        login_saisi = (request.form.get("login") or "").strip()
        mot_de_passe = request.form.get("mot_de_passe") or ""

        conn = db.get_db()
        utilisateur = su.verifier_identifiants(conn, login_saisi, mot_de_passe)

        if utilisateur is None:
            flash("Login ou mot de passe incorrect.", "error")
            current_app.logger.warning("Echec de connexion pour le login : %s", login_saisi)
            return render_template("login.html", login=login_saisi)

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


@auth_bp.route("/mot-de-passe-oublie", methods=["GET", "POST"])
def mot_de_passe_oublie():
    """
    Version simplifiee, sans email (choix assume - voir le commentaire en
    tete de fichier) : login + nouveau mot de passe sur le meme
    formulaire. Le message de confirmation est volontairement le meme,
    que le login existe ou non, pour ne pas laisser deviner l'existence
    d'un compte a partir de son adresse email.
    """
    if request.method == "POST":
        login_saisi = (request.form.get("login") or "").strip()
        nouveau = request.form.get("nouveau_mot_de_passe") or ""
        confirmation = request.form.get("confirmation") or ""

        if nouveau != confirmation:
            flash("Les deux mots de passe saisis ne sont pas identiques.", "error")
            return render_template("mot_de_passe_oublie.html", login=login_saisi)

        if len(nouveau) < su.LONGUEUR_MIN_MOT_DE_PASSE:
            flash("Le mot de passe doit faire au moins %s caracteres." % su.LONGUEUR_MIN_MOT_DE_PASSE, "error")
            return render_template("mot_de_passe_oublie.html", login=login_saisi)

        conn = db.get_db()
        try:
            su.changer_mot_de_passe(conn, login_saisi, nouveau)
            current_app.logger.warning(
                "Mot de passe reinitialise (sans verification par email) pour : %s", login_saisi
            )
        except ValueError:
            # Login inconnu : on ne le revele pas (meme message dans les 2 cas).
            pass

        flash("Si ce compte existe, son mot de passe a ete mis a jour. Vous pouvez maintenant vous connecter.", "ok")
        return redirect(url_for("auth.login"))

    return render_template("mot_de_passe_oublie.html", login="")
