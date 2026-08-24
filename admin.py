# coding: utf8
"""
Ecrans d'administration portes depuis ramasse10_sql.py :
  - Gestion des magasins (fenetre3/fenetre4 -> magasin()/modif_cre()/valid_mag()/sup_mag())
  - Gestion des fournisseurs / articles / types de ramasse (fenetre9,
    un seul ecran generique reutilise 3 fois -> fenetre_fournisseurs()/
    fenetre_articles()/fenetre_types()/charger_clients()/ajout_cli()/
    sup_cli())
  - Epuration de l'historique (fenetre10 -> epuration()/valider_epur())
  - Sauvegarde SQL complete de la base (fonctionnalite absente de
    l'original, voir services/sauvegarde.py) - reservee a l'administrateur
  - Gestion des utilisateurs (fonctionnalite absente de l'original, voir
    services/utilisateurs.py) - reservee a l'administrateur (CODE_BA='00')

Regroupes dans un Blueprint separe de app.py (qui reste centre sur
l'ecran de saisie journaliere) pour garder chaque fichier lisible.

Cloisonnement multi-site (CODE_BA) : la gestion des magasins et
l'epuration de l'historique sont desormais limitees au site (code_ba) de
l'utilisateur connecte (voir auth.utilisateur_courant()) - jamais une
valeur choisie par le navigateur. Les fournisseurs/articles/types restent
un referentiel partage entre tous les sites (pas de CODE_BA sur `param`).
"""
import os

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    current_app, send_from_directory, abort,
)

import db
from auth import admin_required, utilisateur_courant
from services import magasins as sm
from services import parametres as sp
from services import epuration as se
from services import dateutils as du
from services import sauvegarde as ss
from services import utilisateurs as su

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Slug d'URL (lisible) -> code_type stocke dans param.code_type
SLUGS = {"fournisseurs": "F", "articles": "A", "types": "T"}


def _code_type_ou_404(slug):
    if slug not in SLUGS:
        abort(404)
    return SLUGS[slug]


def _code_ba_courant():
    """CODE_BA de l'utilisateur connecte (garanti present : voir auth.py, protection globale des routes)."""
    return utilisateur_courant()["code_ba"]


# --------------------------------------------------------------------- #
# Gestion des magasins (table `modeles`) - limitee au site de l'utilisateur
# --------------------------------------------------------------------- #

@admin_bp.route("/magasins")
def magasins_liste():
    conn = db.get_db()
    magasins = sm.liste_magasins(conn, _code_ba_courant())
    return render_template("admin_magasins.html", magasins=magasins)


def _lire_formulaire_magasin():
    header = {
        "code_ram": (request.form.get("code_ram") or "").strip().upper(),
        "magasin": (request.form.get("magasin") or "").strip(),
        "nom": (request.form.get("nom") or "").strip(),
        "partenaire": (request.form.get("partenaire") or "").strip().upper(),
        "rebut": "O" if request.form.get("rebut") == "on" else "N",
    }
    for jour in sm.JOURS:
        header[jour] = request.form.get(jour) == "on"

    codart = request.form.getlist("codart")
    libart = request.form.getlist("libart")
    depot = request.form.getlist("depot")
    codfour = request.form.getlist("codfour")

    lignes = []
    for i in range(len(codart)):
        # Une ligne totalement vide (ajoutee puis laissee vide) est ignoree
        # plutot que de faire echouer la validation - plus tolerant que de
        # forcer l'utilisateur a la retirer explicitement.
        if not any((codart[i], libart[i], depot[i], codfour[i])):
            continue
        lignes.append({
            "codart": (codart[i] or "").strip(),
            "libart": (libart[i] or "").strip(),
            "depot": (depot[i] or "").strip(),
            "codfour": (codfour[i] or "").strip(),
        })
    return header, lignes


@admin_bp.route("/magasins/nouveau", methods=["GET", "POST"])
def magasin_nouveau():
    conn = db.get_db()
    code_ba = _code_ba_courant()
    types = sm_list_types_safe(conn)

    if request.method == "POST":
        header, lignes = _lire_formulaire_magasin()
        erreurs = sm.valider_magasin(conn, code_ba, header, lignes)
        if erreurs:
            for e in erreurs:
                flash(e, "error")
            return render_template(
                "admin_magasin_form.html", mode="creation", types=types,
                header=header, lignes=lignes or [{}],
            )
        sm.enregistrer_magasin(conn, code_ba, header, lignes)
        current_app.logger.info("Magasin cree : %s %s %s (%s)", code_ba, header["code_ram"], header["magasin"], header["nom"])
        flash("Magasin cree.", "ok")
        return redirect(url_for("admin.magasins_liste"))

    return render_template(
        "admin_magasin_form.html", mode="creation", types=types,
        header={"rebut": "N"}, lignes=[{}],
    )


@admin_bp.route("/magasins/<code_ram>/<magasin>/modifier", methods=["GET", "POST"])
def magasin_modifier(code_ram, magasin):
    conn = db.get_db()
    code_ba = _code_ba_courant()
    types = sm_list_types_safe(conn)

    if request.method == "POST":
        header, lignes = _lire_formulaire_magasin()
        erreurs = sm.valider_magasin(
            conn, code_ba, header, lignes,
            code_ram_existant=code_ram, magasin_existant=magasin,
        )
        if erreurs:
            for e in erreurs:
                flash(e, "error")
            return render_template(
                "admin_magasin_form.html", mode="modification", types=types,
                header=header, lignes=lignes or [{}],
                code_ram_origine=code_ram, magasin_origine=magasin,
            )
        # Si le type ou le code magasin a change, on supprime l'ancien
        # couple pour eviter de laisser un doublon orphelin.
        if (header["code_ram"], str(header["magasin"])) != (code_ram, str(magasin)):
            sm.supprimer_magasin(conn, code_ba, code_ram, magasin)
        sm.enregistrer_magasin(conn, code_ba, header, lignes)
        current_app.logger.info(
            "Magasin modifie : %s %s %s -> %s %s", code_ba, code_ram, magasin, header["code_ram"], header["magasin"]
        )
        flash("Magasin modifie.", "ok")
        return redirect(url_for("admin.magasins_liste"))

    fiche = sm.get_magasin(conn, code_ba, code_ram, magasin)
    if fiche is None:
        flash("Ce magasin n'existe pas (ou plus).", "error")
        return redirect(url_for("admin.magasins_liste"))

    return render_template(
        "admin_magasin_form.html", mode="modification", types=types,
        header=fiche["header"], lignes=fiche["lignes"],
        code_ram_origine=code_ram, magasin_origine=magasin,
    )


@admin_bp.route("/magasins/<code_ram>/<magasin>/supprimer", methods=["POST"])
def magasin_supprimer(code_ram, magasin):
    conn = db.get_db()
    code_ba = _code_ba_courant()
    sm.supprimer_magasin(conn, code_ba, code_ram, magasin)
    current_app.logger.info("Magasin supprime : %s %s %s", code_ba, code_ram, magasin)
    flash("Magasin supprime.", "ok")
    return redirect(url_for("admin.magasins_liste"))


def sm_list_types_safe(conn):
    from services import ramasse as rs
    try:
        return rs.list_types(conn)
    except Exception:
        return []


# --------------------------------------------------------------------- #
# Gestion des fournisseurs / articles / types de ramasse (table `param`)
# Referentiel PARTAGE entre tous les sites (pas de CODE_BA sur `param`).
# --------------------------------------------------------------------- #

@admin_bp.route("/parametres/<slug>")
def parametres_liste(slug):
    code_type = _code_type_ou_404(slug)
    conn = db.get_db()
    entrees = sp.liste(conn, code_type)

    editer = request.args.get("editer")
    fiche_edition = None
    if editer:
        for code, libelle in entrees:
            if code == editer:
                fiche_edition = {"code": code, "libelle": libelle}
                break

    return render_template(
        "admin_parametres.html",
        slug=slug, code_type=code_type, infos=sp.TYPES[code_type],
        entrees=entrees, fiche_edition=fiche_edition,
    )


@admin_bp.route("/parametres/<slug>/ajouter", methods=["POST"])
def parametres_ajouter(slug):
    code_type = _code_type_ou_404(slug)
    conn = db.get_db()
    try:
        sp.creer(conn, code_type, request.form.get("code"), request.form.get("libelle"))
        flash("Enregistrement ajoute.", "ok")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.parametres_liste", slug=slug))


@admin_bp.route("/parametres/<slug>/<code>/modifier", methods=["POST"])
def parametres_modifier(slug, code):
    code_type = _code_type_ou_404(slug)
    conn = db.get_db()
    try:
        sp.modifier(conn, code_type, code, request.form.get("libelle"))
        flash("Enregistrement modifie.", "ok")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.parametres_liste", slug=slug))


@admin_bp.route("/parametres/<slug>/<code>/supprimer", methods=["POST"])
def parametres_supprimer(slug, code):
    code_type = _code_type_ou_404(slug)
    conn = db.get_db()
    try:
        sp.supprimer(conn, code_type, code)
        flash("Enregistrement supprime.", "ok")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.parametres_liste", slug=slug))


# --------------------------------------------------------------------- #
# Epuration de l'historique (table `histo`) - limitee au site de l'utilisateur
# --------------------------------------------------------------------- #

@admin_bp.route("/epuration", methods=["GET", "POST"])
def epuration():
    conn = db.get_db()
    code_ba = _code_ba_courant()

    if request.method == "GET":
        return render_template(
            "admin_epuration.html",
            date_limite=se.date_limite_defaut(),
            confirmation=None,
        )

    date_saisie = (request.form.get("date_limite") or "").strip()
    action = request.form.get("action")
    statut, _, date_norm = du.verif_date(date_saisie)

    if statut != "OK":
        flash("La date saisie est invalide.", "error")
        return render_template("admin_epuration.html", date_limite=date_saisie, confirmation=None)

    date_amj = du.amj(date_norm)

    if action == "confirmer":
        nb = se.epurer(conn, code_ba, date_amj)
        current_app.logger.warning(
            "Epuration de l'historique (site %s) a la date du %s : %s ligne(s) supprimee(s)", code_ba, date_amj, nb
        )
        flash("Epuration terminee, nombre supprime : %s" % nb, "ok")
        return redirect(url_for("admin.epuration"))

    # action == "calculer" (premier passage) : on annonce le nombre de
    # lignes concernees, sans encore rien supprimer.
    nb = se.compter(conn, code_ba, date_amj)
    if nb == 0:
        flash("Aucune ligne d'historique avant le %s." % date_norm, "warning")
        return render_template("admin_epuration.html", date_limite=date_norm, confirmation=None)

    return render_template(
        "admin_epuration.html",
        date_limite=date_norm,
        confirmation={"date_norm": date_norm, "nb": nb},
    )


# --------------------------------------------------------------------- #
# Sauvegarde SQL complete de la base (mysqldump) - reservee a l'administrateur
# (le dump contient les donnees de TOUS les sites, pas seulement le sien).
# --------------------------------------------------------------------- #

@admin_bp.route("/sauvegarde", methods=["GET", "POST"])
@admin_required
def sauvegarde():
    repertoire = current_app.config["CSV_EXPORT_DIR"]

    if request.method == "POST":
        try:
            chemin = ss.creer(current_app.config, repertoire)
            current_app.logger.info("Sauvegarde SQL creee : %s", chemin)
            flash("Sauvegarde creee : %s" % os.path.basename(chemin), "ok")
        except RuntimeError as e:
            current_app.logger.error("Echec de la sauvegarde SQL : %s", e)
            flash(str(e), "error")
        return redirect(url_for("admin.sauvegarde"))

    return render_template(
        "admin_sauvegarde.html", repertoire=repertoire, sauvegardes=ss.lister(repertoire)
    )


@admin_bp.route("/sauvegarde/<nom>/telecharger")
@admin_required
def sauvegarde_telecharger(nom):
    nom = os.path.basename(nom)
    if not (nom.startswith(ss.PREFIXE) and nom.endswith(ss.SUFFIXE)):
        abort(404)

    repertoire = current_app.config["CSV_EXPORT_DIR"]
    if not os.path.isfile(os.path.join(repertoire, nom)):
        abort(404)

    return send_from_directory(repertoire, nom, as_attachment=True)


# --------------------------------------------------------------------- #
# Gestion des utilisateurs (table `user`) - reservee a l'administrateur
# (CODE_BA = '00'), fonctionnalite absente de l'original.
# --------------------------------------------------------------------- #

@admin_bp.route("/utilisateurs")
@admin_required
def utilisateurs_liste():
    conn = db.get_db()
    return render_template("admin_utilisateurs.html", utilisateurs=su.lister(conn))


@admin_bp.route("/utilisateurs/nouveau", methods=["GET", "POST"])
@admin_required
def utilisateur_nouveau():
    if request.method == "POST":
        conn = db.get_db()
        login = request.form.get("login")
        code_ba = request.form.get("code_ba")
        nom_ba = request.form.get("nom_ba")
        try:
            su.creer(conn, login, request.form.get("mot_de_passe"), code_ba, nom_ba)
            current_app.logger.info("Utilisateur cree : %s (CODE_BA %s)", login, code_ba)
            flash("Utilisateur cree.", "ok")
            return redirect(url_for("admin.utilisateurs_liste"))
        except ValueError as e:
            flash(str(e), "error")
            return render_template(
                "admin_utilisateur_form.html", mode="creation",
                utilisateur={"login": login, "code_ba": code_ba, "nom_ba": nom_ba},
            )

    return render_template("admin_utilisateur_form.html", mode="creation", utilisateur={})


@admin_bp.route("/utilisateurs/<login>/modifier", methods=["GET", "POST"])
@admin_required
def utilisateur_modifier(login):
    conn = db.get_db()

    if request.method == "POST":
        code_ba = request.form.get("code_ba")
        nom_ba = request.form.get("nom_ba")
        try:
            su.modifier(conn, login, code_ba, nom_ba)
            nouveau_mdp = request.form.get("nouveau_mot_de_passe") or ""
            if nouveau_mdp:
                su.changer_mot_de_passe(conn, login, nouveau_mdp)
            current_app.logger.info("Utilisateur modifie : %s", login)
            flash("Utilisateur modifie.", "ok")
            return redirect(url_for("admin.utilisateurs_liste"))
        except ValueError as e:
            flash(str(e), "error")
            return render_template(
                "admin_utilisateur_form.html", mode="modification",
                utilisateur={"login": login, "code_ba": code_ba, "nom_ba": nom_ba},
            )

    utilisateur = su.trouver_par_login(conn, login)
    if utilisateur is None:
        flash("Ce compte n'existe pas (ou plus).", "error")
        return redirect(url_for("admin.utilisateurs_liste"))
    return render_template("admin_utilisateur_form.html", mode="modification", utilisateur=utilisateur)


@admin_bp.route("/utilisateurs/<login>/supprimer", methods=["POST"])
@admin_required
def utilisateur_supprimer(login):
    conn = db.get_db()
    try:
        su.supprimer(conn, login)
        current_app.logger.info("Utilisateur supprime : %s", login)
        flash("Utilisateur supprime.", "ok")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.utilisateurs_liste"))
