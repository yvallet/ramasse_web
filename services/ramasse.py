# coding: utf8
"""
Logique metier de la "ramasse journaliere", portee depuis ramasse10_sql.py
(fonctions create_connection/valider_fin/creer_histo/garnir_box/get_list/
page2/suivant/precedent/afficher_suivant/cumul/maj/quit_page2/
valider_page2/controle/exporter).

Difference volontaire par rapport a l'original : toutes les requetes SQL
utilisent des parametres (%s) au lieu d'une concatenation de chaines. Le
programme tkinter construisait ses requetes avec des f-strings / "+"
(ex: "... where code_ram = " + quot + wc + quot), ce qui fonctionne mais
expose a des injections SQL si un code contient un caractere imprevu.
Le comportement observable est identique.
"""
import csv
import os
from datetime import datetime, timedelta

from . import dateutils as du

# ---------------------------------------------------------------------
# Jours geres par la table `modeles` : lundi..vendredi + samedi (ajoute
# plus tard). Pas de colonne dimanche : la ramasse ne tourne jamais un
# dimanche, comme dans le programme d'origine (creer_histo n'a pas de
# branche wjj==6).
# ---------------------------------------------------------------------
JOUR_COLONNES = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]


class ControleError(Exception):
    """Equivalent du texte renvoye par controle() quand rebut > qte."""
    pass


# ----------------------------- Types de ramasse -------------------------

def list_types(conn):
    """param.code_type = 'T'  ->  [(code, libelle), ...] (ex: BA, BOUL, ELOI, CLAM)."""
    cur = conn.cursor()
    cur.execute("select code, libelle from param where code_type = %s order by code", ("T",))
    return cur.fetchall()


# ----------------------------- Suggestion de date ------------------------

def suggest_default_date(conn, code_ram):
    """
    Reprend la logique de fin de script de ramasse10_sql.py qui pre-remplit
    la date au lancement : elle part de la derniere ligne saisie dans
    `histo` pour ce type de ramasse et propose le jour ouvre suivant
    (en sautant le week-end sauf si le samedi est ouvre pour ce type).

    Retourne (date_jj_mm_aaaa, weekday) ou weekday: 0=Lundi..6=Dimanche.
    """
    cur = conn.cursor()

    # Le samedi est-il travaille pour ce type de ramasse ?
    cur.execute(
        "select count(*) from modeles where code_ram = %s and samedi = 1",
        (code_ram,),
    )
    wsamdi = cur.fetchone()[0] or 0

    # Derniere date connue pour ce type (l'original prend le tout dernier
    # id, tous types confondus ; ici on filtre par code_ram, plus correct
    # des lors que l'appli sert plusieurs types de ramasse a la fois)
    cur.execute(
        "select date_ram from histo where code_ram = %s order by id desc limit 1",
        (code_ram,),
    )
    row = cur.fetchone()

    if row is None:
        w = du.date_jour()
        return w, datetime.today().weekday()

    dd = str(row[0])
    w = du.jma(dd)
    dada = datetime.strptime(w, "%d/%m/%Y")
    le_jour = dada.weekday()

    if wsamdi == 0:
        dada = dada + timedelta(days=1 if le_jour < 4 else 3)
    else:
        dada = dada + timedelta(days=1 if le_jour < 5 else 2)

    wd = str(dada)
    w = wd[8:10] + "/" + wd[5:7] + "/" + wd[0:4]
    return w, dada.weekday()


# ----------------------------- Creation de la journee --------------------

def day_exists(conn, code_ram, date_amj):
    cur = conn.cursor()
    cur.execute(
        "select count(*) from histo where code_ram = %s and date_ram = %s",
        (code_ram, date_amj),
    )
    return (cur.fetchone()[0] or 0) > 0


def create_day(conn, code_ram, date_amj, weekday):
    """
    Equivalent de creer_histo(wc, wd, wjj) pour wjj in 0..5 : cree une
    ligne histo (qte=0, rebut=0) pour chaque ligne de modele du type de
    ramasse dont le jour de semaine correspondant est actif.

    weekday: 0=Lundi ... 5=Samedi (Dimanche non gere, comme l'original).
    """
    if weekday not in range(0, 6):
        raise ValueError("La ramasse ne fonctionne pas le dimanche")

    colonne = JOUR_COLONNES[weekday]
    cur = conn.cursor()
    # colonne controlee par nous-memes (whitelist JOUR_COLONNES), jamais
    # une valeur utilisateur -> pas de risque d'injection ici.
    cur.execute(
        f"select * from modeles where code_ram = %s and {colonne} = 1 order by magasin, nolig",
        (code_ram,),
    )
    rows = cur.fetchall()

    cur_ins = conn.cursor()
    for row in rows:
        # modeles: id,code_ram,magasin,nom,lundi,mardi,mercredi,jeudi,
        #          vendredi,codfour,nolig,codart,libart,depot,partenaire,
        #          samedi,rebut
        cur_ins.execute(
            """insert into histo
               (id, code_ram, date_ram, magasin, nom, codfour, nolig, codart, libart, qte, rebut, depot)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (0, row[1], date_amj, row[2], row[3], row[9], row[10], row[11], row[12], 0, 0, row[13]),
        )
    conn.commit()


def add_store(conn, code_ram, date_amj, magasin):
    """Equivalent de creer_histo(wc, wd, 9) : ajoute un magasin non prevu ce jour-la."""
    cur = conn.cursor()
    cur.execute(
        "select * from modeles where code_ram = %s and magasin = %s order by magasin, nolig",
        (code_ram, str(magasin)),
    )
    rows = cur.fetchall()

    cur_ins = conn.cursor()
    for row in rows:
        cur_ins.execute(
            """insert into histo
               (id, code_ram, date_ram, magasin, nom, codfour, nolig, codart, libart, qte, rebut, depot)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (0, row[1], date_amj, row[2], row[3], row[9], row[10], row[11], row[12], 0, 0, row[13]),
        )
    conn.commit()


# ----------------------------- Magasins de la journee ---------------------

def get_scheduled_stores(conn, code_ram, date_amj):
    """Magasins deja presents dans histo pour cette journee, tries par code magasin (= tablo/garnir_box)."""
    cur = conn.cursor()
    cur.execute(
        "select distinct magasin, nom from histo where code_ram = %s and date_ram = %s order by magasin asc",
        (code_ram, date_amj),
    )
    return cur.fetchall()


def get_addable_stores(conn, code_ram, date_amj):
    """Magasins du type de ramasse pas encore presents ce jour-la (pour 'Ajouter un magasin')."""
    scheduled = {str(m) for m, _ in get_scheduled_stores(conn, code_ram, date_amj)}
    cur = conn.cursor()
    cur.execute(
        "select magasin, nom from modeles where code_ram = %s and nolig = 1 order by magasin",
        (code_ram,),
    )
    return [(m, nom) for m, nom in cur.fetchall() if str(m) not in scheduled]


def get_store_lines(conn, code_ram, date_amj, magasin):
    """Lignes histo (jusqu'a 10) du magasin courant, triees par nolig (= contenu de l'ecran de detail)."""
    cur = conn.cursor()
    cur.execute(
        """select id, magasin, nom, nolig, codart, libart, qte, rebut
           from histo where code_ram = %s and date_ram = %s and magasin = %s
           order by nolig""",
        (code_ram, date_amj, str(magasin)),
    )
    cols = ["id", "magasin", "nom", "nolig", "codart", "libart", "qte", "rebut"]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_first_store(conn, code_ram, date_amj):
    cur = conn.cursor()
    cur.execute(
        "select min(magasin) from histo where code_ram = %s and date_ram = %s",
        (code_ram, date_amj),
    )
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else None


def get_adjacent_store(conn, code_ram, date_amj, magasin, sens):
    """
    sens='S' (Suivant) -> plus petit magasin strictement superieur au courant
    sens='P' (Precedent) -> plus grand magasin strictement inferieur au courant
    Retourne None si fin de liste (= message "Pas de suivant/precedent" d'origine).
    """
    cur = conn.cursor()
    if sens == "S":
        cur.execute(
            "select min(magasin) from histo where code_ram = %s and date_ram = %s and magasin > %s",
            (code_ram, date_amj, str(magasin)),
        )
    else:
        cur.execute(
            "select max(magasin) from histo where code_ram = %s and date_ram = %s and magasin < %s",
            (code_ram, date_amj, str(magasin)),
        )
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else None


# ----------------------------- Sauvegarde / controle ----------------------

def validate_lines(lines):
    """
    Equivalent de controle() : rebut ne doit jamais depasser la quantite,
    ligne par ligne. Renvoie un message d'erreur (str) ou None si OK.
    """
    for line in lines:
        qte = float(line["qte"] or 0)
        rebut = float(line["rebut"] or 0)
        if rebut > qte:
            libelle = line.get("libart") or ("Ligne-%s" % line.get("nolig"))
            return "Incoherence sur %s : le rebut (%.3f) est superieur a la quantite (%.3f). Corrigez !" % (
                libelle, rebut, qte,
            )
    return None


def save_lines(conn, lines):
    """Equivalent de maj() : met a jour qte/rebut de chaque ligne (par id)."""
    cur = conn.cursor()
    for line in lines:
        cur.execute(
            "update histo set qte = %s, rebut = %s where id = %s",
            (line["qte"], line["rebut"], line["id"]),
        )
    conn.commit()


def store_total(lines):
    """Somme des quantites saisies pour un magasin (pour la confirmation 'aucun poids saisi')."""
    return sum(float(l["qte"] or 0) for l in lines)


def cumul_totals(conn, code_ram, date_amj, codarts, exclude_magasin=None):
    """
    Equivalent de cumul(wc, wd, codart) applique a une liste de codes
    article : total (qte - rebut) toutes lignes/tous magasins confondus
    pour cette journee, par article (= colonne "Totaux" de l'ecran 2).

    exclude_magasin (optionnel) : exclut entierement ce magasin du calcul
    (equivalent de cumul2, mais sur tout le magasin plutot qu'une seule
    ligne : voir _totaux_hors_magasin ci-dessous, utilisee pour la mise a
    jour en direct du total pendant la saisie).
    """
    if not codarts:
        return {}
    cur = conn.cursor()
    placeholders = ",".join(["%s"] * len(codarts))
    sql = f"""select codart, sum(qte - rebut) from histo
              where code_ram = %s and date_ram = %s and codart in ({placeholders})"""
    params = [code_ram, date_amj, *codarts]
    if exclude_magasin is not None:
        sql += " and magasin != %s"
        params.append(str(exclude_magasin))
    sql += " group by codart"
    cur.execute(sql, params)
    return {codart: round(float(total or 0), 3) for codart, total in cur.fetchall()}


def totaux_hors_magasin(conn, code_ram, date_amj, magasin, codarts):
    """
    Pour chaque code article de `codarts` : le total (qte - rebut) deja
    enregistre pour TOUS LES AUTRES magasins ce jour-la (le magasin
    courant est exclu entierement, y compris ses valeurs deja
    sauvegardees). C'est la "base" sur laquelle le navigateur ajoute, en
    direct et sans recharger la page, la saisie en cours du magasin
    affiche a l'ecran (voir static/detail.js) - equivalent de cumul2()
    dans le programme d'origine, qui recalculait ce total a chaque sortie
    de champ.
    """
    return cumul_totals(conn, code_ram, date_amj, codarts, exclude_magasin=magasin)


# ----------------------------- Fin de journee -----------------------------

def day_total(conn, code_ram, date_amj):
    cur = conn.cursor()
    cur.execute(
        "select sum(qte) from histo where code_ram = %s and date_ram = %s",
        (code_ram, date_amj),
    )
    row = cur.fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


def delete_day(conn, code_ram, date_amj):
    """Equivalent de la purge dans quit_page2 quand tout est a zero."""
    cur = conn.cursor()
    cur.execute(
        "delete from histo where code_ram = %s and date_ram = %s",
        (code_ram, date_amj),
    )
    conn.commit()


def empty_stores(conn, code_ram, date_amj):
    """
    Equivalent de la boucle de valider_page2 qui repere les magasins dont
    le total saisi est a zero, pour demander confirmation ('Attention rien
    de saisi pour X, vous confirmez ?').
    """
    cur = conn.cursor()
    cur.execute(
        """select magasin, nom, sum(qte) from histo
           where code_ram = %s and date_ram = %s
           group by magasin, nom order by magasin""",
        (code_ram, date_amj),
    )
    return [nom for _, nom, total in cur.fetchall() if not total]


# ----------------------------- Export CSV (VIF) ---------------------------

_NOMS_FICHIERS_ACHAT = {"BA": "ramas", "ELOI": "rameloi", "BOUL": "boulang", "CLAM": "clamcy"}
_NOMS_FICHIERS_REBUT = {"BA": "rebut", "ELOI": "rebeloi", "BOUL": "rebboul"}


def export_csv(conn, code_ram, date_amj, csv_dir, code_ba):
    """
    Port fidele de exporter() : genere les 2 fichiers CSV attendus par
    l'import VIF (reception + rebuts), au meme format ';' / encodage ANSI.
    Retourne (nom_fichier_achat_ou_None, nb_lignes_achat, nom_fichier_rebut_ou_None, nb_lignes_rebut).
    """
    os.makedirs(csv_dir, exist_ok=True)

    dada = du.jma(date_amj)  # jj/mm/aaaa
    jj, mm = dada[0:2], dada[3:5]

    cur = conn.cursor()
    cur.execute(
        "select * from histo where code_ram = %s and date_ram = %s order by magasin asc, nolig",
        (code_ram, date_amj),
    )
    rows = cur.fetchall()
    # histo: id,code_ram,date_ram,magasin,nom,codfour,nolig,codart,libart,qte,rebut,depot

    achat, divers = [], []

    for enr in rows:
        wqte, wrebut = enr[9], enr[10]
        codfour = enr[5]
        if len(codfour) == 7:
            codfour = "0" + codfour
        codart = enr[7]
        if len(codart) == 6:
            codart = "0" + codart
        loti = codart[6:7]
        libfour = enr[4]
        depot = enr[11]
        un = "KG"
        lot = "" if loti == "0" else (code_ba + "RA" + codart)
        origine = "RA"

        if wqte == 0:
            continue

        dt = datetime.strptime(dada, "%d/%m/%Y") + timedelta(days=2)
        dluo = du.jma(str(dt)[0:10])

        cur_p = conn.cursor()
        cur_p.execute(
            "select partenaire from modeles where code_ram = %s and codfour = %s and nolig = 1",
            (code_ram, codfour),
        )
        p = cur_p.fetchone()
        lib_partenaire = p[0] if p else ""

        achat.append([
            "01", code_ba, dada, codfour, "01", depot, codart,
            str(wqte).replace(".", ","), un, lot, origine, dluo, dluo, lib_partenaire,
        ])

        if wrebut == 0:
            continue

        if not divers:
            divers.append([
                "Ste;BA;1OD;0;0;Nat;10/02/2023;Hre;LIB;Motif;Tiers;Code;1;2;3;4;5;6;7;8;9;10;11;"
                "codart;LOT;depot;emplact;Qte;Unit;1;2;3;4;5;6;7;8;9;10;11;12;ORIGINE;OR"
            ])

        wlib = ("REBUT " + libfour)[:30]
        divers.append([
            "01", code_ba, "1OD", "0", "0", "MV-REBUT", dada, "", wlib, "R03", "FRS", codfour,
            "", "", "", "", "", "", "", "", "", "", "", codart, lot, depot, "",
            str(wrebut).replace(".", ","), un,
            "", "", "", "", "", "", "", "", "", "", "", "",
            "ORIGINE", origine,
        ])

    nom_achat = nb_achat = None
    if achat:
        nom_achat = _NOMS_FICHIERS_ACHAT.get(code_ram, code_ram) + jj + mm + ".csv"
        with open(os.path.join(csv_dir, nom_achat), mode="w", newline="", encoding="cp1252", errors="replace") as f:
            csv.writer(f, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL).writerows(achat)
        nb_achat = len(achat)

    nom_rebut = nb_rebut = None
    if divers:
        prefix = _NOMS_FICHIERS_REBUT.get(code_ram, "reb" + code_ram)
        nom_rebut = prefix + jj + mm + ".csv"
        with open(os.path.join(csv_dir, nom_rebut), mode="w", newline="", encoding="cp1252", errors="replace") as f:
            csv.writer(f, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL).writerows(divers)
        nb_rebut = len(divers) - 1  # la 1ere ligne est l'entete

    return nom_achat, nb_achat, nom_rebut, nb_rebut
