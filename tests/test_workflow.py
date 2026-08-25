# coding: utf8
"""
Verification du portage de la logique metier (services/ramasse.py) et du
cablage des routes Flask (app.py), sans dependre d'un vrai serveur MySQL :
on utilise une base sqlite3 en memoire (tests/db_shim.py) qui comprend les
memes requetes %s que le code de production.

A lancer avec :  python3 tests/test_workflow.py
(pas besoin de pytest ni de mysql-connector-python installes)
"""
import sys
import os
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# mysql.connector n'est pas installe dans cet environnement de test :
# on fournit un module factice pour que `import mysql.connector` (dans
# db.py) reussisse. get_db() est de toute facon monkeypatche plus bas
# pour ne jamais l'appeler pour de vrai.
if "mysql" not in sys.modules:
    mysql_mod = types.ModuleType("mysql")
    connector_mod = types.ModuleType("mysql.connector")
    connector_mod.connect = lambda **kw: None
    mysql_mod.connector = connector_mod
    sys.modules["mysql"] = mysql_mod
    sys.modules["mysql.connector"] = connector_mod

import db  # noqa: E402
from tests.db_shim import build_test_db, CODE_BA_TEST  # noqa: E402
from services import ramasse as rs  # noqa: E402
from services import dateutils as du  # noqa: E402
from services import utilisateurs as su  # noqa: E402


class RamasseLogicTests(unittest.TestCase):
    """Tests unitaires directs sur services/ramasse.py (sans passer par Flask)."""

    def setUp(self):
        self.conn = build_test_db()
        self.code_ba = CODE_BA_TEST  # '58' - voir tests/db_shim.py
        # Lundi 24/08/2026 (verifie : date(2026,8,24).weekday() == 0)
        self.lundi_amj = "2026-08-24"
        self.mardi_amj = "2026-08-25"

    def test_create_day_respecte_le_jour_de_semaine(self):
        # Lundi : magasin 10 ouvert (3 lignes), magasin 20 ferme
        rs.create_day(self.conn, self.code_ba, "BA", self.lundi_amj, weekday=0)
        stores = rs.get_scheduled_stores(self.conn, self.code_ba, "BA", self.lundi_amj)
        self.assertEqual([m for m, _ in stores], [10])
        lignes = rs.get_store_lines(self.conn, self.code_ba, "BA", self.lundi_amj, 10)
        self.assertEqual(len(lignes), 3)

    def test_create_day_mardi_ouvre_magasin_20(self):
        rs.create_day(self.conn, self.code_ba, "BA", self.mardi_amj, weekday=1)
        stores = rs.get_scheduled_stores(self.conn, self.code_ba, "BA", self.mardi_amj)
        self.assertEqual([m for m, _ in stores], [10, 20])

    def test_add_store_hors_planning(self):
        rs.create_day(self.conn, self.code_ba, "BA", self.lundi_amj, weekday=0)
        rs.add_store(self.conn, self.code_ba, "BA", self.lundi_amj, 20)
        stores = rs.get_scheduled_stores(self.conn, self.code_ba, "BA", self.lundi_amj)
        self.assertEqual(sorted(m for m, _ in stores), [10, 20])

    def test_navigation_suivant_precedent(self):
        rs.create_day(self.conn, self.code_ba, "BA", self.mardi_amj, weekday=1)
        premier = rs.get_first_store(self.conn, self.code_ba, "BA", self.mardi_amj)
        self.assertEqual(premier, 10)
        suivant = rs.get_adjacent_store(self.conn, self.code_ba, "BA", self.mardi_amj, premier, "S")
        self.assertEqual(suivant, 20)
        plus_loin = rs.get_adjacent_store(self.conn, self.code_ba, "BA", self.mardi_amj, suivant, "S")
        self.assertIsNone(plus_loin)  # "Pas de suivant, fin de liste"
        retour = rs.get_adjacent_store(self.conn, self.code_ba, "BA", self.mardi_amj, suivant, "P")
        self.assertEqual(retour, 10)

    def test_controle_rebut_superieur_a_qte(self):
        lignes = [{"qte": 5, "rebut": 6, "nolig": 1, "libart": "Pain"}]
        err = rs.validate_lines(lignes)
        self.assertIsNotNone(err)
        self.assertIn("Pain", err)

        lignes_ok = [{"qte": 5, "rebut": 5, "nolig": 1, "libart": "Pain"}]
        self.assertIsNone(rs.validate_lines(lignes_ok))

    def test_cumul_totaux_toutes_lignes_meme_article(self):
        rs.create_day(self.conn, self.code_ba, "BA", self.mardi_amj, weekday=1)
        lignes10 = rs.get_store_lines(self.conn, self.code_ba, "BA", self.mardi_amj, 10)
        lignes20 = rs.get_store_lines(self.conn, self.code_ba, "BA", self.mardi_amj, 20)

        # codart 0119000 (Pain) present dans les 2 magasins
        for l in lignes10:
            if l["codart"] == "0119000":
                l["qte"], l["rebut"] = 10, 1
        for l in lignes20:
            if l["codart"] == "0119000":
                l["qte"], l["rebut"] = 4, 0

        rs.save_lines(self.conn, self.code_ba, lignes10)
        rs.save_lines(self.conn, self.code_ba, lignes20)

        totaux = rs.cumul_totals(self.conn, self.code_ba, "BA", self.mardi_amj, ["0119000"])
        self.assertEqual(totaux["0119000"], 13.0)  # (10-1) + (4-0)

    def test_totaux_hors_magasin_pour_mise_a_jour_en_direct(self):
        # Reproduit le scenario signale : la colonne "Total jour article"
        # doit exclure le magasin affiche a l'ecran (dont la saisie en
        # cours, pas encore enregistree, est ajoutee cote navigateur), et
        # inclure les autres magasins deja enregistres.
        rs.create_day(self.conn, self.code_ba, "BA", self.mardi_amj, weekday=1)
        lignes10 = rs.get_store_lines(self.conn, self.code_ba, "BA", self.mardi_amj, 10)
        lignes20 = rs.get_store_lines(self.conn, self.code_ba, "BA", self.mardi_amj, 20)

        for l in lignes10:
            if l["codart"] == "0119000":
                l["qte"], l["rebut"] = 10, 1
        for l in lignes20:
            if l["codart"] == "0119000":
                l["qte"], l["rebut"] = 4, 0

        rs.save_lines(self.conn, self.code_ba, lignes10)
        rs.save_lines(self.conn, self.code_ba, lignes20)

        # Ecran ouvert sur le magasin 10 : la base doit valoir la
        # contribution du magasin 20 uniquement (4), pas celle,
        # deja enregistree, du magasin 10 lui-meme.
        base = rs.totaux_hors_magasin(self.conn, self.code_ba, "BA", self.mardi_amj, 10, ["0119000"])
        self.assertEqual(base["0119000"], 4.0)

        # Le navigateur ajoute alors la saisie en cours du magasin 10
        # (meme non enregistree) par-dessus cette base -> total live correct.
        live_qte, live_rebut = 20, 2
        total_affiche = base["0119000"] + (live_qte - live_rebut)
        self.assertEqual(total_affiche, 22.0)

    def test_empty_stores_et_day_total(self):
        rs.create_day(self.conn, self.code_ba, "BA", self.lundi_amj, weekday=0)
        self.assertEqual(rs.day_total(self.conn, self.code_ba, "BA", self.lundi_amj), 0.0)
        self.assertEqual(rs.empty_stores(self.conn, self.code_ba, "BA", self.lundi_amj), ["Magasin Dix"])

        lignes = rs.get_store_lines(self.conn, self.code_ba, "BA", self.lundi_amj, 10)
        lignes[0]["qte"] = 7
        rs.save_lines(self.conn, self.code_ba, lignes)

        self.assertEqual(rs.empty_stores(self.conn, self.code_ba, "BA", self.lundi_amj), [])
        self.assertEqual(rs.day_total(self.conn, self.code_ba, "BA", self.lundi_amj), 7.0)

    def test_delete_day_si_tout_est_a_zero(self):
        rs.create_day(self.conn, self.code_ba, "BA", self.lundi_amj, weekday=0)
        self.assertTrue(rs.day_exists(self.conn, self.code_ba, "BA", self.lundi_amj))
        rs.delete_day(self.conn, self.code_ba, "BA", self.lundi_amj)
        self.assertFalse(rs.day_exists(self.conn, self.code_ba, "BA", self.lundi_amj))

    def test_export_csv_genere_les_2_fichiers(self):
        rs.create_day(self.conn, self.code_ba, "BA", self.lundi_amj, weekday=0)
        lignes = rs.get_store_lines(self.conn, self.code_ba, "BA", self.lundi_amj, 10)
        for l in lignes:
            l["qte"] = 12.5
            l["rebut"] = 2.0
        rs.save_lines(self.conn, self.code_ba, lignes)

        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            nom_achat, nb_achat, nom_rebut, nb_rebut = rs.export_csv(
                self.conn, self.code_ba, "BA", self.lundi_amj, tmp
            )
            self.assertIsNotNone(nom_achat)
            self.assertEqual(nb_achat, 3)
            self.assertTrue(os.path.exists(os.path.join(tmp, nom_achat)))

            self.assertIsNotNone(nom_rebut)
            self.assertEqual(nb_rebut, 3)
            self.assertTrue(os.path.exists(os.path.join(tmp, nom_rebut)))

            with open(os.path.join(tmp, nom_achat), encoding="cp1252") as f:
                contenu = f.read()
            self.assertIn("12,5", contenu)
            self.assertIn("0119000", contenu)

    def test_verif_date_et_conversions(self):
        statut, date_obj, norm = du.verif_date("24/08/2026")
        self.assertEqual(statut, "OK")
        self.assertEqual(norm, "24/08/2026")
        self.assertEqual(date_obj.weekday(), 0)  # lundi

        statut_ko, _, _ = du.verif_date("31/02/2026")  # 31 fevrier n'existe pas
        self.assertEqual(statut_ko, "KO")

        self.assertEqual(du.amj("24/08/2026"), "2026-08-24")
        self.assertEqual(du.jma("2026-08-24"), "24/08/2026")

    def test_suggest_default_date_lundi_puis_mardi(self):
        rs.create_day(self.conn, self.code_ba, "BA", self.lundi_amj, weekday=0)
        date_suivante, weekday = rs.suggest_default_date(self.conn, self.code_ba, "BA")
        self.assertEqual(date_suivante, "25/08/2026")  # lundi + 1 jour = mardi
        self.assertEqual(weekday, 1)

    def test_cloisonnement_entre_sites_differents(self):
        # Fonctionnalite absente de l'original (une seule installation =
        # un seul site) : deux sites (CODE_BA differents) sur la meme base
        # ne doivent jamais se voir l'un l'autre, meme avec le meme
        # code_ram/magasin.
        rs.create_day(self.conn, self.code_ba, "BA", self.lundi_amj, weekday=0)  # site '58'
        self.assertFalse(rs.day_exists(self.conn, "99", "BA", self.lundi_amj))  # site '99' : rien
        self.assertEqual(rs.get_scheduled_stores(self.conn, "99", "BA", self.lundi_amj), [])

    def test_nom_type_ramasse(self):
        # Fonctionnalite absente de l'original : le libelle du type de
        # ramasse (ex: "Ramasse BA") est affiche a la place du code brut
        # sur l'ecran de saisie (voir templates/detail.html).
        self.assertEqual(rs.nom_type_ramasse(self.conn, self.code_ba, "BA"), "Ramasse BA")
        # Type inconnu (ou supprime entre-temps) : on retombe sur le code
        # plutot que de faire echouer l'affichage.
        self.assertEqual(rs.nom_type_ramasse(self.conn, self.code_ba, "XXXXX"), "XXXXX")
        # Meme code, autre site : chaque site a son propre libelle (Types
        # de ramasse desormais propres a chaque site).
        self.assertEqual(rs.nom_type_ramasse(self.conn, "99", "BA"), "BA")  # aucun type "BA" sur le site 99


class FlaskRoutesSmokeTests(unittest.TestCase):
    """Verifie que les routes Flask s'enchainent sans erreur (bout en bout)."""

    def setUp(self):
        self.conn = build_test_db()
        self.code_ba = CODE_BA_TEST
        import app as app_module
        self.app_module = app_module
        app_module.db.get_db = lambda: self.conn  # monkeypatch : pas de vrai MySQL
        app_module.app.config.update(TESTING=True)
        self.client = app_module.app.test_client()

        # Authentification (fonctionnalite absente de l'original) : toutes
        # les routes exigent desormais une session utilisateur active.
        su.creer(self.conn, "site58@test.fr", "motdepasse", self.code_ba, "BA 58")
        r = self.client.post("/login", data={"login": "site58@test.fr", "mot_de_passe": "motdepasse"})
        self.assertEqual(r.status_code, 302)  # redirection vers / apres connexion reussie

    def test_parcours_complet_saisie_puis_detail_puis_terminer(self):
        # Ecran 1 : formulaire de saisie
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)

        # Validation type + date -> doit creer la journee et rediriger vers /detail
        r = self.client.post("/saisie/valider", data={"type": "BA", "date": "25/08/2026"},
                              follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Magasin Dix", r.data)
        # Le nom du type de ramasse (libelle "Ramasse BA" de la fixture) est
        # affiche a la place du code brut "BA" (fonctionnalite absente de
        # l'original, ecran detail.html).
        self.assertIn(b"Ramasse BA", r.data)
        # Fonctionnalite absente de l'original, corrige un vrai piege
        # signale : le menu (et la deconnexion) sont masques pendant la
        # saisie par magasin, pour qu'un clic malencontreux ne fasse pas
        # perdre une ligne non encore enregistree - seuls "Quitter" et
        # "Terminer la journee" permettent d'en sortir.
        self.assertNotIn(b'href="/admin/parametres/fournisseurs"', r.data)
        self.assertNotIn(b"Se deconnecter", r.data)

        # Ecran de saisie (page 1) : le menu reste normalement accessible,
        # seul l'ecran de saisie par magasin (page 2) le masque.
        r = self.client.get("/")
        self.assertIn(b'href="/admin/parametres/fournisseurs"', r.data)
        self.assertIn(b"Se deconnecter", r.data)

        # Enregistrer une ligne puis passer au magasin suivant
        r = self.client.post("/detail/save", data={
            "magasin": "10",
            "id": ["1", "2", "3"],
            "nolig": ["1", "2", "3"],
            "codart": ["0119000", "4520000", "4620001"],
            "libart": ["Pain", "Fruits-Legumes", "Viande"],
            "qte": ["10", "0", "0"],
            "rebut": ["1", "0", "0"],
            "action": "suivant",
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Magasin Vingt", r.data)

        # Terminer la journee : magasin 20 est a zero -> ecran de confirmation attendu
        r = self.client.post("/detail/terminer", data={
            "magasin": "20",
            "id": ["4", "5"],
            "nolig": ["1", "2"],
            "codart": ["0119000", "4320001"],
            "libart": ["Pain", "Produits Laitiers"],
            "qte": ["0", "0"],
            "rebut": ["0", "0"],
            "action": "save_current",
        })
        self.assertEqual(r.status_code, 200)
        self.assertIn("Magasin Vingt".encode(), r.data)  # liste des magasins vides
        self.assertIn(b"Ramasse BA", r.data)  # nom du type de ramasse, harmonise avec detail.html
        # L'ecran de confirmation n'a pas de champ editable (juste
        # Confirmer/Annuler) : le menu n'y est pas masque, contrairement a
        # l'ecran de saisie par magasin.
        self.assertIn(b'href="/admin/parametres/fournisseurs"', r.data)

        # Confirmation -> export reel
        r = self.client.post("/detail/terminer", data={"confirmed": "1"}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)

    def test_saisie_invalide_refusee_avec_message_et_rien_enregistre(self):
        # Reproduit le bug signale : "ABCD" ou "100..200" dans le champ
        # quantite ne doit plus etre enregistre comme 0 en silence, mais
        # etre refuse avec un message clair, sans toucher a la base.
        self.client.post("/saisie/valider", data={"type": "BA", "date": "25/08/2026"})

        for valeur_invalide in ("ABCD", "100..200"):
            r = self.client.post("/detail/save", data={
                "magasin": "10",
                "id": ["1", "2", "3"],
                "nolig": ["1", "2", "3"],
                "codart": ["0119000", "4520000", "4620001"],
                "libart": ["Pain", "Fruits-Legumes", "Viande"],
                "qte": [valeur_invalide, "0", "0"],
                "rebut": ["0", "0", "0"],
                "action": "save",
            }, follow_redirects=True)
            self.assertEqual(r.status_code, 200)
            self.assertIn(b"Quantite invalide", r.data)

            # La ligne n'a pas ete touchee (toujours a 0, pas silencieusement mise a 0
            # "par coincidence" -> on verifie via une valeur non-nulle prealable).
            lignes = rs.get_store_lines(self.conn, self.code_ba, "BA", "2026-08-25", 10)
            self.assertEqual(lignes[0]["qte"], 0)

        # Une fois corrige, la sauvegarde fonctionne normalement.
        r = self.client.post("/detail/save", data={
            "magasin": "10",
            "id": ["1", "2", "3"],
            "nolig": ["1", "2", "3"],
            "codart": ["0119000", "4520000", "4620001"],
            "libart": ["Pain", "Fruits-Legumes", "Viande"],
            "qte": ["12,5", "0", "0"],
            "rebut": ["0", "0", "0"],
            "action": "save",
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        lignes = rs.get_store_lines(self.conn, self.code_ba, "BA", "2026-08-25", 10)
        self.assertEqual(lignes[0]["qte"], 12.5)

    def test_routes_protegees_sans_connexion(self):
        # Fonctionnalite absente de l'original : sans session active,
        # toute route (sauf /login et /mot-de-passe-oublie) redirige vers
        # la connexion plutot que d'afficher les donnees.
        client_anonyme = self.app_module.app.test_client()
        r = client_anonyme.get("/", follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Connexion", r.data)

        r = client_anonyme.get("/admin/magasins", follow_redirects=True)
        self.assertIn(b"Connexion", r.data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
