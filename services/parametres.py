# coding: utf8
"""
Gestion des 3 listes de codes stockees dans la table `param` : Fournisseurs
(code_type='F'), Articles ('A'), Types de ramasse ('T').

Porte depuis ramasse10_sql.py : voir_fournisseurs/fenetre_fournisseurs/
fenetre_articles/fenetre_types/charger_clients/ajout_cli/sup_cli/
modif_cli/sortir_client (un seul ecran generique dans l'original,
reutilise 3 fois - meme principe ici).

Difference volontaire : l'original n'implementait PAS la modification
(`modif_cli()` est un stub qui affiche juste "modif" et ne fait rien -
seuls Ajouter et Supprimer fonctionnaient, il fallait supprimer puis
recreer pour changer un libelle). Ce portage ajoute une vraie
modification (`update`), simple mise a jour du libelle.
"""

TYPES = {
    "F": {"nom": "Fournisseurs", "longueur_code": 8,
          "regle": "Le code fournisseur doit faire exactement 8 caracteres."},
    "A": {"nom": "Articles", "longueur_code": 7,
          "regle": "Le code article doit faire exactement 7 caracteres."},
    "T": {"nom": "Types de ramasse", "longueur_code_max": 5,
          "regle": "Le code type doit faire 5 caracteres maximum "
                    "(contrainte du nom de fichier d'export VIF)."},
}


def liste(conn, code_type):
    """[(code, libelle), ...] pour un code_type donne, triees par code."""
    cur = conn.cursor()
    cur.execute(
        "select code, libelle from param where code_type = %s order by code",
        (code_type,),
    )
    return cur.fetchall()


def existe(conn, code_type, code):
    cur = conn.cursor()
    cur.execute(
        "select count(*) from param where code_type = %s and code = %s",
        (code_type, code),
    )
    return (cur.fetchone()[0] or 0) > 0


def valider_code(code_type, code):
    """
    Reprend les controles de longueur de ajout_cli() par type. Renvoie un
    message d'erreur (str) ou None si le code est valide.
    """
    regles = TYPES[code_type]
    if code_type in ("F", "A") and len(code) != regles["longueur_code"]:
        return regles["regle"]
    if code_type == "T" and len(code) > regles["longueur_code_max"]:
        return regles["regle"]
    return None


def creer(conn, code_type, code, libelle):
    """Equivalent de ajout_cli(). Leve ValueError si invalide ou deja existant."""
    code = (code or "").strip().upper()
    libelle = (libelle or "").strip()

    if not code:
        raise ValueError("Il faut indiquer le code.")
    if not libelle:
        raise ValueError("Il faut indiquer le libelle.")

    erreur = valider_code(code_type, code)
    if erreur:
        raise ValueError(erreur)

    if existe(conn, code_type, code):
        raise ValueError("Ajout impossible : ce code existe deja.")

    cur = conn.cursor()
    cur.execute(
        "insert into param (id, code_type, code, libelle) values (%s, %s, %s, %s)",
        (0, code_type, code, libelle),
    )
    conn.commit()


def modifier(conn, code_type, code, libelle):
    """
    Met a jour le libelle d'un code existant (fonctionnalite absente de
    l'original, cf. note en tete de fichier).
    """
    libelle = (libelle or "").strip()
    if not libelle:
        raise ValueError("Il faut indiquer le libelle.")
    if not existe(conn, code_type, code):
        raise ValueError("Modification impossible : ce code n'existe pas.")

    cur = conn.cursor()
    cur.execute(
        "update param set libelle = %s where code_type = %s and code = %s",
        (libelle, code_type, code),
    )
    conn.commit()


def compter_usages_magasins(conn, code_type, code):
    """
    Nombre de lignes de `modeles` qui referencent ce code (article ou
    fournisseur) - sert a avertir avant suppression, sans bloquer (comme
    l'original, qui ne verifiait aucune reference avant de supprimer).
    """
    colonne = {"A": "codart", "F": "codfour", "T": "code_ram"}.get(code_type)
    if colonne is None:
        return 0
    cur = conn.cursor()
    cur.execute(f"select count(distinct magasin) from modeles where {colonne} = %s", (code,))  # nosec: colonne whitelistee
    return cur.fetchone()[0] or 0


def supprimer(conn, code_type, code):
    """Equivalent de sup_cli(). Leve ValueError si le code n'existe pas."""
    if not existe(conn, code_type, code):
        raise ValueError("Suppression impossible : ce code n'existe pas.")
    cur = conn.cursor()
    cur.execute(
        "delete from param where code_type = %s and code = %s",
        (code_type, code),
    )
    conn.commit()
