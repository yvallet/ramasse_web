# coding: utf8
"""
Ramasse journaliere - version web (Flask), portage de ramasse10_sql.py :
  - Page 1 (saisie) : choix du type de ramasse + date de tournee
  - Page 2 (detail) : saisie des quantites/rebuts par magasin, navigation
    Suivant/Precedent, ajout d'un magasin non prevu, validation de fin de
    journee (export CSV VIF) ou sortie sans export.
  - Administration (voir admin.py) : gestion des magasins, des
    fournisseurs, des articles et des types de ramasse.

Ecrans NON repris (deliberement, hors du perimetre convenu) : epuration
de l'historique, sauvegarde, impression d'etiquettes / bon de reception
PDF. Ils reposent sur le meme schema MySQL et pourront etre ajoutes de la
meme maniere par la suite.
"""
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template, request, redirect, url_for, session, flash

import db
from config import Config
from services import dateutils as du
from services import ramasse as rs


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    _configurer_logs(app)

    from admin import admin_bp
    app.register_blueprint(admin_bp)

    return app


def _configurer_logs(app):
    """
    Log d'execution persistant (equivalent du LOG.log de l'original, ecrit
    par get_logger()/logger.warning() dans outils.py). Ecrit dans
    logs/app.log a cote de app.py, avec rotation pour ne pas grossir sans
    fin. Recupere aussi les erreurs non interceptees (exceptions) qui,
    avant, ne laissaient aucune trace pour l'utilisateur.
    """
    log_dir = app.config.get("LOG_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    chemin = os.path.join(log_dir, "app.log")

    handler = RotatingFileHandler(chemin, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
    ))
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info("Demarrage de l'application (log : %s)", chemin)


app = create_app()


# --------------------------------------------------------------------- #
# Page 1 : choix du type de ramasse + date (= combo/entree_date/valider_fin)
# --------------------------------------------------------------------- #

@app.route("/", methods=["GET"])
def saisie():
    conn = db.get_db()
    types = list_types_safe(conn)

    code_ram = request.args.get("type", "")
    date_defaut, weekday = ("", None)
    if code_ram:
        date_defaut, weekday = rs.suggest_default_date(conn, code_ram)
    else:
        date_defaut = du.date_jour()
        weekday = datetime.today().weekday()

    return render_template(
        "saisie.html",
        types=types,
        code_ram=code_ram,
        date_defaut=date_defaut,
        nom_jour=du.nom_jour(weekday) if weekday is not None else "",
    )


def list_types_safe(conn):
    try:
        return rs.list_types(conn)
    except Exception:
        return []


@app.route("/saisie/valider", methods=["POST"])
def saisie_valider():
    conn = db.get_db()
    code_ram = (request.form.get("type") or "").strip()
    date_saisie = (request.form.get("date") or "").strip()

    if not code_ram:
        flash("Il faut d'abord choisir le type de ramasse.", "error")
        return redirect(url_for("saisie"))

    statut, date_obj, date_norm = du.verif_date(date_saisie)
    if statut != "OK":
        flash("La date saisie est invalide.", "error")
        return redirect(url_for("saisie", type=code_ram))

    weekday = date_obj.weekday()  # 0=Lundi ... 6=Dimanche
    if weekday == 6:
        flash("Il n'y a pas de ramasse le dimanche.", "error")
        return redirect(url_for("saisie", type=code_ram))

    date_amj = du.amj(date_norm)

    if not rs.day_exists(conn, code_ram, date_amj):
        rs.create_day(conn, code_ram, date_amj, weekday)

    premier = rs.get_first_store(conn, code_ram, date_amj)
    if premier is None:
        flash(
            "Aucun magasin programme ce jour-la pour ce type de ramasse. "
            "Vous pouvez en ajouter un manuellement depuis l'ecran suivant.",
            "warning",
        )

    session["code_ram"] = code_ram
    session["date_amj"] = date_amj
    session["date_norm"] = date_norm
    session.pop("magasin", None)

    return redirect(url_for("detail", magasin=premier) if premier else url_for("detail"))


# --------------------------------------------------------------------- #
# Page 2 : detail par magasin (= page2/afficher_suivant/garnir_box)
# --------------------------------------------------------------------- #

def _contexte_session():
    code_ram = session.get("code_ram")
    date_amj = session.get("date_amj")
    if not code_ram or not date_amj:
        return None, None
    return code_ram, date_amj


@app.route("/detail", methods=["GET"])
def detail():
    conn = db.get_db()
    code_ram, date_amj = _contexte_session()
    if not code_ram:
        flash("Choisissez d'abord un type de ramasse et une date.", "error")
        return redirect(url_for("saisie"))

    scheduled = rs.get_scheduled_stores(conn, code_ram, date_amj)
    if not scheduled:
        flash("Aucun magasin pour cette journee. Ajoutez-en un ou changez de date.", "warning")

    magasin = request.args.get("magasin") or session.get("magasin")
    if magasin is None and scheduled:
        magasin = scheduled[0][0]

    lines, totals, totaux_hors_magasin, nom_magasin = [], {}, {}, ""
    has_prev = has_next = None
    if magasin is not None:
        lines = rs.get_store_lines(conn, code_ram, date_amj, magasin)
        codarts = [l["codart"] for l in lines]
        totals = rs.cumul_totals(conn, code_ram, date_amj, codarts)
        # Base servant au recalcul en direct cote navigateur (voir detail.js) :
        # total de TOUS LES AUTRES magasins pour cet article, sur laquelle le
        # navigateur ajoute la saisie en cours du magasin affiche, ligne par
        # ligne, sans recharger la page (equivalent de cumul2() a chaque
        # sortie de champ dans le programme d'origine).
        totaux_hors_magasin = rs.totaux_hors_magasin(conn, code_ram, date_amj, magasin, codarts)
        nom_magasin = lines[0]["nom"] if lines else ""
        has_prev = rs.get_adjacent_store(conn, code_ram, date_amj, magasin, "P")
        has_next = rs.get_adjacent_store(conn, code_ram, date_amj, magasin, "S")
        session["magasin"] = magasin

    addable = rs.get_addable_stores(conn, code_ram, date_amj)

    return render_template(
        "detail.html",
        code_ram=code_ram,
        date_norm=session.get("date_norm", du.jma(date_amj)),
        scheduled=scheduled,
        addable=addable,
        magasin=magasin,
        nom_magasin=nom_magasin,
        lines=lines,
        totals=totals,
        totaux_hors_magasin=totaux_hors_magasin,
        has_prev=has_prev,
        has_next=has_next,
    )


def _parse_nombre(texte):
    """
    Convertit un champ quantite/rebut saisi en nombre. Un champ vide vaut 0
    (comme dans l'original : cf. after_qte5 qui fait `if len(lst)==0: lst="0"`).
    Une valeur qui n'est pas un nombre ("ABCD", "100..200"...) est signalee
    comme invalide au lieu d'etre silencieusement remplacee par 0 - c'est le
    bug corrige ici : avant, une saisie invalide etait enregistree comme 0
    sans aucun message (contrairement a l'original, qui affichait
    "Quantite invalide" via anomalie() dans after_qteN/after_rebutN).

    Retourne (valeur_float, texte_original_si_invalide_sinon_None).
    """
    brut = (texte or "").strip()
    if brut == "":
        return 0.0, None
    try:
        return float(brut.replace(",", ".")), None
    except ValueError:
        return 0.0, brut


def _lire_lignes_soumises():
    """
    Relit les champs qte[]/rebut[]/id[]/nolig[]/codart[]/libart[] postes
    par le formulaire de detail.

    Retourne (lignes, erreurs) : `erreurs` liste les messages a afficher
    pour toute quantite/rebut qui n'est pas un nombre valide - dans ce cas
    la ligne correspondante n'est PAS enregistree (voir les appelants).
    """
    ids = request.form.getlist("id")
    nolig = request.form.getlist("nolig")
    codart = request.form.getlist("codart")
    libart = request.form.getlist("libart")
    qte = request.form.getlist("qte")
    rebut = request.form.getlist("rebut")

    lignes = []
    erreurs = []
    for i in range(len(ids)):
        libelle = libart[i] or ("ligne %s" % nolig[i])

        q, brut_q = _parse_nombre(qte[i])
        if brut_q is not None:
            erreurs.append('Quantite invalide pour "%s" : "%s" n\'est pas un nombre.' % (libelle, brut_q))

        r, brut_r = _parse_nombre(rebut[i])
        if brut_r is not None:
            erreurs.append('Rebut invalide pour "%s" : "%s" n\'est pas un nombre.' % (libelle, brut_r))

        lignes.append({
            "id": ids[i],
            "nolig": nolig[i],
            "codart": codart[i],
            "libart": libart[i],
            "qte": q,
            "rebut": r,
        })
    return lignes, erreurs


@app.route("/detail/save", methods=["POST"])
def detail_save():
    """
    Point d'entree unique pour Enregistrer / Suivant / Precedent
    (= maj() + controle() + afficher_suivant()).
    """
    conn = db.get_db()
    code_ram, date_amj = _contexte_session()
    if not code_ram:
        return redirect(url_for("saisie"))

    magasin = request.form.get("magasin")
    action = request.form.get("action")  # save | suivant | precedent
    lignes, erreurs_saisie = _lire_lignes_soumises()

    if erreurs_saisie:
        for msg in erreurs_saisie:
            flash(msg, "error")
        app.logger.warning(
            "Saisie invalide, rien n'est enregistre - %s %s magasin %s : %s",
            code_ram, date_amj, magasin, " | ".join(erreurs_saisie),
        )
        return redirect(url_for("detail", magasin=magasin))

    erreur = rs.validate_lines(lignes)
    if erreur:
        flash(erreur, "error")
        return redirect(url_for("detail", magasin=magasin))

    rs.save_lines(conn, lignes)

    if action == "suivant":
        cible = rs.get_adjacent_store(conn, code_ram, date_amj, magasin, "S")
        if cible is None:
            flash("Pas de suivant, fin de liste.", "warning")
            return redirect(url_for("detail", magasin=magasin))
        return redirect(url_for("detail", magasin=cible))

    if action == "precedent":
        cible = rs.get_adjacent_store(conn, code_ram, date_amj, magasin, "P")
        if cible is None:
            flash("Pas de precedent, fin de liste.", "warning")
            return redirect(url_for("detail", magasin=magasin))
        return redirect(url_for("detail", magasin=cible))

    flash("Enregistre.", "ok")
    return redirect(url_for("detail", magasin=magasin))


@app.route("/detail/add_store", methods=["POST"])
def detail_add_store():
    """Equivalent du clic sur un magasin non prevu dans la listbox (creer_histo(..., 9))."""
    conn = db.get_db()
    code_ram, date_amj = _contexte_session()
    if not code_ram:
        return redirect(url_for("saisie"))

    magasin = request.form.get("nouveau_magasin")
    if magasin:
        rs.add_store(conn, code_ram, date_amj, magasin)
        return redirect(url_for("detail", magasin=magasin))

    flash("Choisissez un magasin a ajouter.", "error")
    return redirect(url_for("detail"))


@app.route("/detail/quitter", methods=["POST"])
def detail_quitter():
    """Equivalent de quit_page2() : sortie sans export, purge si tout est a zero."""
    conn = db.get_db()
    code_ram, date_amj = _contexte_session()
    if not code_ram:
        return redirect(url_for("saisie"))

    if rs.day_total(conn, code_ram, date_amj) == 0:
        rs.delete_day(conn, code_ram, date_amj)
        flash("Journee vide : aucune ligne enregistree, elle a ete supprimee.", "warning")
    else:
        flash("Sortie sans export des fichiers.", "warning")

    session.pop("code_ram", None)
    session.pop("date_amj", None)
    session.pop("date_norm", None)
    session.pop("magasin", None)
    return redirect(url_for("saisie"))


@app.route("/detail/terminer", methods=["GET", "POST"])
def detail_terminer():
    """Equivalent de valider_page2() : verif magasins vides puis exporter()."""
    conn = db.get_db()
    code_ram, date_amj = _contexte_session()
    if not code_ram:
        return redirect(url_for("saisie"))

    if request.method == "POST" and request.form.get("action") == "save_current":
        magasin = request.form.get("magasin")
        lignes, erreurs_saisie = _lire_lignes_soumises()

        if erreurs_saisie:
            for msg in erreurs_saisie:
                flash(msg, "error")
            app.logger.warning(
                "Saisie invalide, rien n'est enregistre - %s %s magasin %s : %s",
                code_ram, date_amj, magasin, " | ".join(erreurs_saisie),
            )
            return redirect(url_for("detail", magasin=magasin))

        erreur = rs.validate_lines(lignes)
        if erreur:
            flash(erreur, "error")
            return redirect(url_for("detail", magasin=magasin))
        rs.save_lines(conn, lignes)

    vides = rs.empty_stores(conn, code_ram, date_amj)
    if vides and request.form.get("confirmed") != "1":
        return render_template(
            "confirmer_fin.html",
            code_ram=code_ram,
            date_norm=session.get("date_norm", du.jma(date_amj)),
            vides=vides,
        )

    nom_achat, nb_achat, nom_rebut, nb_rebut = rs.export_csv(
        conn, code_ram, date_amj, app.config["CSV_EXPORT_DIR"], app.config["CODE_BA"]
    )

    msg = "Fichiers a importer : reception = %s (%s lignes), rebuts = %s (%s lignes)" % (
        nom_achat or "aucun", nb_achat or 0, nom_rebut or "aucun", nb_rebut or 0,
    )
    flash(msg, "ok")

    session.pop("code_ram", None)
    session.pop("date_amj", None)
    session.pop("date_norm", None)
    session.pop("magasin", None)
    return redirect(url_for("saisie"))


if __name__ == "__main__":
    app.run(debug=True)
