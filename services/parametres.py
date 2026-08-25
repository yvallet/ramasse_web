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

Cloisonnement multi-site (CODE_BA) : fonctionnalite absente de l'original,
ajoutee en 2 temps (voir migration_login_multi_ba.sql puis
migration_param_code_ba.sql). Fournisseurs et Types de ramasse sont
desormais propres a chaque site : toutes les fonctions ci-dessous prennent
`code_ba` en 2e parametre (le CODE_BA de l'utilisateur connecte, voir
auth.py - jamais une valeur choisie par le navigateur), et chaque acces est
limite aux enregistrements de ce site. EXCEPTION explicitement demandee :
les Articles restent un referentiel PARTAGE entre tous les sites (colonne
`code_ba` laissee a NULL en base pour ces lignes) - `code_ba` est alors
simplement ignore, comme avant l'ajout du cloisonnement.
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

# code_type dont les enregistrements sont propres a un site (code_ba
# renseigne et pris en compte). 'A' (Articles) n'y figure pas : referentiel
# partage entre tous les sites, code_ba toujours NULL pour ces lignes -
# voir la note en tete de fichier.
_TYPES_CLOISONNES = ("F", "T")


def liste(conn, code_ba, code_type):
    """[(code, libelle), ...] pour un code_type donne (et, sauf Articles, un site donne), triees par code."""
    cur = conn.cursor()
    if code_type in _TYPES_CLOISONNES:
        cur.execute(
            "select code, libelle from param where code_ba = %s and code_type = %s order by code",
            (code_ba, code_type),
        )
    else:
        cur.execute(
            "select code, libelle from param where code_type = %s order by code",
            (code_type,),
        )
    return cur.fetchall()


def existe(conn, code_ba, code_type, code):
    cur = conn.cursor()
    if code_type in _TYPES_CLOISONNES:
        cur.execute(
            "select count(*) from param where code_ba = %s and code_type = %s and code = %s",
            (code_ba, code_type, code),
        )
    else:
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


def creer(conn, code_ba, code_type, code, libelle):
    """
    Equivalent de ajout_cli(). Leve ValueError si invalide, ou si le code
    existe deja (sur ce site pour Fournisseurs/Types ; sur l'ensemble du
    referentiel partage pour Articles).
    """
    code = (code or "").strip().upper()
    libelle = (libelle or "").strip()

    if not code:
        raise ValueError("Il faut indiquer le code.")
    if not libelle:
        raise ValueError("Il faut indiquer le libelle.")

    erreur = valider_code(code_type, code)
    if erreur:
        raise ValueError(erreur)

    if existe(conn, code_ba, code_type, code):
        raise ValueError("Ajout impossible : ce code existe deja.")

    # Articles : referentiel partage, code_ba jamais renseigne (voir note
    # en tete de fichier), meme si un CODE_BA de site est passe en argument.
    code_ba_stocke = code_ba if code_type in _TYPES_CLOISONNES else None

    cur = conn.cursor()
    cur.execute(
        "insert into param (id, code_ba, code_type, code, libelle) values (%s, %s, %s, %s, %s)",
        (0, code_ba_stocke, code_type, code, libelle),
    )
    conn.commit()


def modifier(conn, code_ba, code_type, code, libelle):
    """
    Met a jour le libelle d'un code existant (fonctionnalite absente de
    l'original, cf. note en tete de fichier). Pour Fournisseurs/Types,
    limite au site courant : un utilisateur ne peut pas modifier le
    fournisseur/type d'un AUTRE site, meme en devinant son code.
    """
    libelle = (libelle or "").strip()
    if not libelle:
        raise ValueError("Il faut indiquer le libelle.")
    if not existe(conn, code_ba, code_type, code):
        raise ValueError("Modification impossible : ce code n'existe pas.")

    cur = conn.cursor()
    if code_type in _TYPES_CLOISONNES:
        cur.execute(
            "update param set libelle = %s where code_ba = %s and code_type = %s and code = %s",
            (libelle, code_ba, code_type, code),
        )
    else:
        cur.execute(
            "update param set libelle = %s where code_type = %s and code = %s",
            (libelle, code_type, code),
        )
    conn.commit()


def compter_usages_magasins(conn, code_ba, code_type, code):
    """
    Nombre de magasins (distincts) qui referencent ce code (article,
    fournisseur ou type de ramasse) - sert a avertir avant suppression,
    sans bloquer (comme l'original, qui ne verifiait aucune reference
    avant de supprimer). Pour Fournisseurs/Types (propres a un site), la
    recherche est limitee aux magasins de ce meme site ; pour Articles
    (partages), elle porte sur les magasins de tous les sites.
    """
    colonne = {"A": "codart", "F": "codfour", "T": "code_ram"}.get(code_type)
    if colonne is None:
        return 0
    cur = conn.cursor()
    if code_type in _TYPES_CLOISONNES:
        cur.execute(
            f"select count(distinct magasin) from modeles where code_ba = %s and {colonne} = %s",  # nosec: colonne whitelistee
            (code_ba, code),
        )
    else:
        cur.execute(f"select count(distinct magasin) from modeles where {colonne} = %s", (code,))  # nosec: colonne whitelistee
    return cur.fetchone()[0] or 0


def supprimer(conn, code_ba, code_type, code):
    """Equivalent de sup_cli(). Leve ValueError si le code n'existe pas (sur ce site pour Fournisseurs/Types)."""
    if not existe(conn, code_ba, code_type, code):
        raise ValueError("Suppression impossible : ce code n'existe pas.")
    cur = conn.cursor()
    if code_type in _TYPES_CLOISONNES:
        cur.execute(
            "delete from param where code_ba = %s and code_type = %s and code = %s",
            (code_ba, code_type, code),
        )
    else:
        cur.execute(
            "delete from param where code_type = %s and code = %s",
            (code_type, code),
        )
    conn.commit()
