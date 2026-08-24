# coding: utf8
"""
Gestion des magasins (table `modeles`), portee depuis ramasse10_sql.py :
magasin()/charger_magasins()/ajout_mag()/modif_mag()/modif_cre()/
valid_mag()/sup_mag()/verifart()/veriffour()/veriftype().

Un "magasin" au sens de cet ecran, c'est un couple (type de ramasse,
code magasin) avec un nom, des jours de collecte (lundi..samedi), et une
liste de lignes (1 par article collecte : code article, designation,
depot, fournisseur). C'est exactement ce que decrit chaque groupe de
lignes `modeles` partageant le meme (code_ba, code_ram, magasin).

Differences volontaires par rapport a l'original :
- Cloisonnement multi-site (CODE_BA) : fonctionnalite absente de
  l'original. Toutes les fonctions ci-dessous prennent desormais
  `code_ba` en premier parametre (le CODE_BA de l'utilisateur connecte,
  voir auth.py) : un utilisateur ne voit et ne modifie que les magasins
  de son propre site. Le referentiel articles/fournisseurs/types (table
  `param`, voir services/parametres.py) reste en revanche partage entre
  tous les sites.
- Le type de ramasse (code_ram) est choisi dans une liste (les types deja
  crees via la gestion des types) plutot que saisi en texte libre que
  l'original ne controlait pas (veriftype() existe mais n'est jamais
  appelee sur ce champ dans valid_mag()).
- A la creation, on verifie que le couple (type, magasin) n'existe pas
  deja pour ce site - l'original inserait des lignes en double sans le
  signaler.
- Le champ "code fournisseur" d'en-tete de la fiche magasin (wcodfour/
  zcodfour dans l'original) etait valide (8 caracteres + code existant)
  mais jamais utilise pour l'enregistrement (chaque ligne a son propre
  fournisseur, seul utilise a la sauvegarde) - retire ici, c'etait un
  champ mort.
- Le nombre de lignes n'est plus plafonne a 10 : le formulaire web
  permet d'ajouter/retirer des lignes librement.
"""

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]
PARTENAIRES_VALIDES = ("", "COMERSO", "PHENIX")


def liste_magasins(conn, code_ba):
    """Equivalent de charger_magasins() : un magasin par ligne (nolig=1), pour le tableau recapitulatif."""
    cur = conn.cursor()
    cur.execute(
        """select code_ram, magasin, nom, lundi, mardi, mercredi, jeudi, vendredi, samedi
           from modeles where code_ba = %s and nolig = 1 order by code_ram, magasin""",
        (code_ba,),
    )
    cols = ["code_ram", "magasin", "nom", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def magasin_existe(conn, code_ba, code_ram, magasin):
    cur = conn.cursor()
    cur.execute(
        "select count(*) from modeles where code_ba = %s and code_ram = %s and magasin = %s",
        (code_ba, code_ram, str(magasin)),
    )
    return (cur.fetchone()[0] or 0) > 0


def get_magasin(conn, code_ba, code_ram, magasin):
    """
    Equivalent de la partie chargement de modif_cre() : renvoie
    {header: {...}, lignes: [...]}  ou None si le magasin n'existe pas
    pour ce site.
    """
    cur = conn.cursor()
    cur.execute(
        """select magasin, nom, partenaire, rebut, lundi, mardi, mercredi, jeudi, vendredi, samedi,
                  nolig, codart, libart, depot, codfour
           from modeles where code_ba = %s and code_ram = %s and magasin = %s
           order by nolig""",
        (code_ba, code_ram, str(magasin)),
    )
    rows = cur.fetchall()
    if not rows:
        return None

    premiere = rows[0]
    header = {
        "code_ram": code_ram,
        "magasin": premiere[0],
        "nom": premiere[1],
        "partenaire": premiere[2] or "",
        "rebut": premiere[3] or "N",
        "lundi": bool(premiere[4]),
        "mardi": bool(premiere[5]),
        "mercredi": bool(premiere[6]),
        "jeudi": bool(premiere[7]),
        "vendredi": bool(premiere[8]),
        "samedi": bool(premiere[9]),
    }
    lignes = [
        {"nolig": r[10], "codart": r[11], "libart": r[12], "depot": r[13], "codfour": r[14]}
        for r in rows
    ]
    return {"header": header, "lignes": lignes}


def verifier_article(conn, code):
    """Equivalent de verif()/verifart() : le code existe-t-il dans param('A')? Renvoie (ok, libelle).
    Referentiel partage entre tous les sites (pas de CODE_BA sur `param`)."""
    cur = conn.cursor()
    cur.execute("select libelle from param where code_type = 'A' and code = %s", (code,))
    row = cur.fetchone()
    return (True, row[0]) if row else (False, None)


def verifier_fournisseur(conn, code):
    """Equivalent de verif2()/veriffour(). Referentiel partage entre tous les sites."""
    cur = conn.cursor()
    cur.execute("select libelle from param where code_type = 'F' and code = %s", (code,))
    row = cur.fetchone()
    return (True, row[0]) if row else (False, None)


def valider_magasin(conn, code_ba, header, lignes, code_ram_existant=None, magasin_existant=None):
    """
    Equivalent de la section controle de valid_mag(). Renvoie la liste des
    messages d'erreur (vide si tout est valide). `code_ram_existant`/
    `magasin_existant` : si fournis (cas modification), on autorise ce
    couple a "deja exister" (c'est lui-meme) - la comparaison reste au
    sein du site courant (`code_ba`), deja implicite partout ailleurs.
    """
    erreurs = []

    if not header.get("code_ram"):
        erreurs.append("Choisissez un type de ramasse.")
    if not str(header.get("magasin") or "").strip():
        erreurs.append("Indiquez le code du magasin.")
    elif not str(header.get("magasin")).strip().lstrip("-").isdigit():
        erreurs.append("Le code du magasin doit etre un nombre.")

    if len(header.get("nom") or "") < 2:
        erreurs.append("Saisissez un nom de magasin (2 caracteres minimum).")

    if header.get("partenaire", "") not in PARTENAIRES_VALIDES:
        erreurs.append("Partenaire : laisser vide, ou choisir COMERSO / PHENIX.")

    if header.get("rebut") not in ("O", "N"):
        erreurs.append("Rebut : O ou N.")

    if not lignes:
        erreurs.append("Il faut au moins une ligne d'article.")

    for i, ligne in enumerate(lignes, start=1):
        codart = (ligne.get("codart") or "").strip()
        libart = (ligne.get("libart") or "").strip()
        depot = (ligne.get("depot") or "").strip()
        codfour = (ligne.get("codfour") or "").strip()

        if len(codart) != 7:
            erreurs.append(f"Ligne {i} : le code article doit faire 7 caracteres.")
        elif not verifier_article(conn, codart)[0]:
            erreurs.append(f"Ligne {i} : le code article {codart} n'existe pas (voir Gestion des articles).")

        if not libart:
            erreurs.append(f"Ligne {i} : saisissez un libelle d'article.")
        if not depot:
            erreurs.append(f"Ligne {i} : saisissez un depot.")

        if len(codfour) != 8:
            erreurs.append(f"Ligne {i} : le code fournisseur doit faire 8 caracteres.")
        elif not verifier_fournisseur(conn, codfour)[0]:
            erreurs.append(f"Ligne {i} : le code fournisseur {codfour} n'existe pas (voir Gestion des fournisseurs).")

    if not erreurs:
        # Couple (type, magasin) deja pris par un AUTRE magasin de ce site ?
        cible_existe = magasin_existe(conn, code_ba, header["code_ram"], header["magasin"])
        est_lui_meme = (
            code_ram_existant is not None
            and str(code_ram_existant) == str(header["code_ram"])
            and str(magasin_existant) == str(header["magasin"])
        )
        if cible_existe and not est_lui_meme:
            erreurs.append(
                "Ce magasin existe deja pour ce type de ramasse : utilisez Modifier plutot que Creer."
            )

    return erreurs


def enregistrer_magasin(conn, code_ba, header, lignes):
    """
    Equivalent de la partie enregistrement de valid_mag() : remplace
    entierement les lignes `modeles` du magasin (delete puis insert), que
    ce soit une creation ou une modification - plus simple et plus sur
    qu'un suivi ligne a ligne, et le nombre de lignes peut changer.
    Suppose que valider_magasin() a deja ete appelee avec succes.
    """
    cur = conn.cursor()
    cur.execute(
        "delete from modeles where code_ba = %s and code_ram = %s and magasin = %s",
        (code_ba, header["code_ram"], str(header["magasin"])),
    )

    for i, ligne in enumerate(lignes, start=1):
        cur.execute(
            """insert into modeles
               (code_ram, code_ba, magasin, nom, lundi, mardi, mercredi, jeudi, vendredi,
                codfour, nolig, codart, libart, depot, partenaire, samedi, rebut)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                header["code_ram"], code_ba, str(header["magasin"]), header["nom"],
                1 if header.get("lundi") else 0,
                1 if header.get("mardi") else 0,
                1 if header.get("mercredi") else 0,
                1 if header.get("jeudi") else 0,
                1 if header.get("vendredi") else 0,
                ligne["codfour"], i, ligne["codart"], ligne["libart"], ligne["depot"],
                header.get("partenaire", ""),
                1 if header.get("samedi") else 0,
                header.get("rebut", "N"),
            ),
        )
    conn.commit()


def supprimer_magasin(conn, code_ba, code_ram, magasin):
    """Equivalent de sup_mag()."""
    cur = conn.cursor()
    cur.execute(
        "delete from modeles where code_ba = %s and code_ram = %s and magasin = %s",
        (code_ba, code_ram, str(magasin)),
    )
    conn.commit()
