# coding: utf8
"""
Tests des ecrans d'administration (magasins / fournisseurs / articles /
types de ramasse / epuration de l'historique / sauvegarde SQL), ajoutes a
la suite de ramasse10_sql.py : magasin()/valid_mag()/sup_mag(),
fenetre_fournisseurs()/fenetre_articles()/fenetre_types()/ajout_cli()/
sup_cli(), epuration()/valider_epur(), et la sauvegarde SQL (fonction
absente de l'original, voir services/sauvegarde.py).

A lancer avec : python3 tests/test_admin.py
(ou via test_workflow.py qui importe deja le shim mysql.connector)
"""
import sys
import os
import shutil
import tempfile
import types
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if "mysql" not in sys.modules:
    mysql_mod = types.ModuleType("mysql")
    connector_mod = types.ModuleType("mysql.connector")
    connector_mod.connect = lambda **kw: None
    mysql_mod.connector = connector_mod
    sys.modules["mysql"] = mysql_mod
    sys.modules["mysql.connector"] = connector_mod

from tests.db_shim import build_test_db  # noqa: E402
from services import parametres as sp  # noqa: E402
from services import magasins as sm  # noqa: E402
from services import epuration as se  # noqa: E402
from services import sauvegarde as sv  # noqa: E402


class ParametresTests(unittest.TestCase):
    """services/parametres.py - fournisseurs / articles / types (table `param`)."""

    def setUp(self):
        self.conn = build_test_db()

    def test_liste_filtre_par_type(self):
        fournisseurs = sp.liste(self.conn, "F")
        self.assertEqual(len(fournisseurs), 2)
        types_ram = sp.liste(self.conn, "T")
        self.assertEqual(types_ram, [("BA", "Ramasse BA")])

    def test_creer_et_relire(self):
        sp.creer(self.conn, "T", "eloi", "Ramasse Saint Eloi")  # minuscule -> mis en majuscule
        types_ram = dict(sp.liste(self.conn, "T"))
        self.assertEqual(types_ram["ELOI"], "Ramasse Saint Eloi")

    def test_creer_refuse_code_deja_existant(self):
        with self.assertRaises(ValueError):
            sp.creer(self.conn, "T", "BA", "Doublon")

    def test_creer_refuse_longueur_invalide(self):
        with self.assertRaises(ValueError):
            sp.creer(self.conn, "F", "123", "Trop court")  # fournisseur : 8 caracteres attendus
        with self.assertRaises(ValueError):
            sp.creer(self.conn, "A", "12345678", "Trop long")  # article : 7 caracteres attendus
        with self.assertRaises(ValueError):
            sp.creer(self.conn, "T", "TROPLONG1", "Type trop long")  # type : 5 caracteres max

    def test_modifier_libelle(self):
        sp.modifier(self.conn, "T", "BA", "Nouveau libelle")
        self.assertEqual(dict(sp.liste(self.conn, "T"))["BA"], "Nouveau libelle")

    def test_modifier_code_inexistant_refuse(self):
        with self.assertRaises(ValueError):
            sp.modifier(self.conn, "T", "XXXXX", "peu importe")

    def test_supprimer(self):
        sp.creer(self.conn, "T", "CLAM", "Clamecy")
        sp.supprimer(self.conn, "T", "CLAM")
        self.assertNotIn("CLAM", dict(sp.liste(self.conn, "T")))

    def test_supprimer_code_inexistant_refuse(self):
        with self.assertRaises(ValueError):
            sp.supprimer(self.conn, "T", "XXXXX")

    def test_compter_usages_magasins(self):
        # 0119000 (Pain) est utilise par les 2 magasins de la fixture (10 et 20)
        self.assertEqual(sp.compter_usages_magasins(self.conn, "A", "0119000"), 2)
        self.assertEqual(sp.compter_usages_magasins(self.conn, "A", "9999999"), 0)


class MagasinsTests(unittest.TestCase):
    """services/magasins.py - gestion des magasins (table `modeles`)."""

    def setUp(self):
        self.conn = build_test_db()

    def test_liste_magasins(self):
        magasins = sm.liste_magasins(self.conn)
        self.assertEqual(len(magasins), 2)
        noms = {m["magasin"]: m["nom"] for m in magasins}
        self.assertEqual(noms[10], "Magasin Dix")
        self.assertEqual(noms[20], "Magasin Vingt")

    def test_get_magasin_existant(self):
        fiche = sm.get_magasin(self.conn, "BA", 10)
        self.assertIsNotNone(fiche)
        self.assertEqual(fiche["header"]["nom"], "Magasin Dix")
        self.assertTrue(fiche["header"]["lundi"])
        self.assertFalse(fiche["header"]["mardi"] is True and False)  # sanity
        self.assertEqual(len(fiche["lignes"]), 3)

    def test_get_magasin_absent(self):
        self.assertIsNone(sm.get_magasin(self.conn, "BA", 999))

    def _magasin_valide(self):
        header = {
            "code_ram": "BA", "magasin": "30", "nom": "Nouveau Magasin",
            "partenaire": "", "rebut": "N",
            "lundi": True, "mardi": False, "mercredi": True,
            "jeudi": False, "vendredi": True, "samedi": False,
        }
        lignes = [{"codart": "0119000", "libart": "Pain", "depot": "03", "codfour": "02580004"}]
        return header, lignes

    def test_validation_ok(self):
        header, lignes = self._magasin_valide()
        self.assertEqual(sm.valider_magasin(self.conn, header, lignes), [])

    def test_validation_refuse_article_inconnu(self):
        header, lignes = self._magasin_valide()
        lignes[0]["codart"] = "9999999"
        erreurs = sm.valider_magasin(self.conn, header, lignes)
        self.assertTrue(any("code article" in e for e in erreurs))

    def test_validation_refuse_fournisseur_inconnu(self):
        header, lignes = self._magasin_valide()
        lignes[0]["codfour"] = "99999999"
        erreurs = sm.valider_magasin(self.conn, header, lignes)
        self.assertTrue(any("fournisseur" in e for e in erreurs))

    def test_validation_refuse_sans_ligne(self):
        header, _ = self._magasin_valide()
        erreurs = sm.valider_magasin(self.conn, header, [])
        self.assertTrue(any("au moins une ligne" in e for e in erreurs))

    def test_validation_refuse_doublon_a_la_creation(self):
        header, lignes = self._magasin_valide()
        header["magasin"] = "10"  # deja utilise par 'Magasin Dix'
        erreurs = sm.valider_magasin(self.conn, header, lignes)
        self.assertTrue(any("existe deja" in e for e in erreurs))

    def test_validation_autorise_le_meme_couple_en_modification(self):
        header, lignes = self._magasin_valide()
        header["magasin"] = "10"
        header["nom"] = "Magasin Dix (renomme)"
        erreurs = sm.valider_magasin(self.conn, header, lignes, code_ram_existant="BA", magasin_existant="10")
        self.assertEqual(erreurs, [])

    def test_creation_puis_lecture(self):
        header, lignes = self._magasin_valide()
        sm.enregistrer_magasin(self.conn, header, lignes)
        fiche = sm.get_magasin(self.conn, "BA", "30")
        self.assertEqual(fiche["header"]["nom"], "Nouveau Magasin")
        self.assertEqual(len(fiche["lignes"]), 1)

    def test_modification_remplace_les_lignes(self):
        header = sm.get_magasin(self.conn, "BA", 10)["header"]
        header["nom"] = "Magasin Dix Renomme"
        nouvelles_lignes = [{"codart": "4620001", "libart": "Viande", "depot": "03", "codfour": "02580004"}]
        sm.enregistrer_magasin(self.conn, header, nouvelles_lignes)

        fiche = sm.get_magasin(self.conn, "BA", 10)
        self.assertEqual(fiche["header"]["nom"], "Magasin Dix Renomme")
        self.assertEqual(len(fiche["lignes"]), 1)  # 3 lignes -> remplacees par 1 seule

    def test_suppression(self):
        sm.supprimer_magasin(self.conn, "BA", 10)
        self.assertIsNone(sm.get_magasin(self.conn, "BA", 10))
        # le magasin 20 n'est pas touche
        self.assertIsNotNone(sm.get_magasin(self.conn, "BA", 20))


def _inserer_histo(conn, date_ram, code_ram="BA", magasin=10, codart="0119000"):
    cur = conn.cursor()
    cur.execute(
        """insert into histo
           (id, code_ram, date_ram, magasin, nom, codfour, nolig, codart, libart, qte, rebut, depot)
           values (%s, %s, %s, %s, 'Magasin Dix', '02580004', 1, %s, 'Pain', 5, 0, '03')""",
        (0, code_ram, date_ram, magasin, codart),
    )
    conn.commit()


class EpurationTests(unittest.TestCase):
    """services/epuration.py - purge de l'historique (table `histo`)."""

    def setUp(self):
        self.conn = build_test_db()
        for date_ram in ("2025-11-01", "2025-12-15", "2026-06-01"):
            _inserer_histo(self.conn, date_ram)

    def test_date_limite_defaut_a_le_bon_format(self):
        # Pas de date figee possible ici (pas de mock d'horloge) : on
        # verifie juste que le format jj/mm/aaaa attendu par verif_date()
        # est bien produit.
        self.assertRegex(se.date_limite_defaut(), r"^\d{2}/\d{2}/\d{4}$")

    def test_compter(self):
        self.assertEqual(se.compter(self.conn, "2026-01-01"), 2)  # les 2 lignes de 2025
        self.assertEqual(se.compter(self.conn, "2025-01-01"), 0)  # aucune ligne avant 2025

    def test_epurer_supprime_et_renvoie_le_nombre(self):
        nb = se.epurer(self.conn, "2026-01-01")
        self.assertEqual(nb, 2)
        self.assertEqual(se.compter(self.conn, "2027-01-01"), 1)  # ne reste que la ligne de 2026-06-01

    def test_epuration_ne_filtre_pas_par_code_ram(self):
        # Comme dans l'original : la purge n'est pas limitee a un type de
        # ramasse en particulier - une ligne d'un AUTRE type ('XX') avant
        # la date limite doit aussi etre supprimee.
        _inserer_histo(self.conn, "2025-01-01", code_ram="XX", magasin=20)
        nb = se.epurer(self.conn, "2026-01-01")
        self.assertEqual(nb, 3)


class _FauxResultat:
    """Imite subprocess.CompletedProcess pour les tests (pas de vrai mysqldump ici)."""

    def __init__(self, returncode=0, stderr=b""):
        self.returncode = returncode
        self.stderr = stderr


class SauvegardeTests(unittest.TestCase):
    """
    services/sauvegarde.py - dump SQL complet via mysqldump. Comme cet
    environnement de test n'a pas de vrai mysqldump/serveur MySQL, la
    fonction `executer` (equivalent de subprocess.run) est simulee.
    """

    def setUp(self):
        self.dossier = tempfile.mkdtemp()
        self.config = {
            "MYSQL_HOST": "localhost", "MYSQL_PORT": 3306, "MYSQL_USER": "root",
            "MYSQL_PASSWORD": "secret", "MYSQL_DB": "yvallet_base", "MYSQLDUMP_PATH": "mysqldump",
        }

    def tearDown(self):
        shutil.rmtree(self.dossier, ignore_errors=True)

    def test_nom_fichier_au_format_attendu(self):
        horodatage = datetime(2026, 1, 5, 8, 7)
        self.assertEqual(sv.nom_fichier(horodatage), "sauvegarde-05012026_0807.sql")

    def test_lister_vide_si_dossier_absent(self):
        self.assertEqual(sv.lister(os.path.join(self.dossier, "inexistant")), [])

    def test_lister_ne_garde_que_les_sauvegardes_triees_par_date_desc(self):
        for nom in ("sauvegarde-01012026_0800.sql", "sauvegarde-02012026_0800.sql", "autre_fichier.csv"):
            with open(os.path.join(self.dossier, nom), "w") as f:
                f.write("x")
        noms = [e["nom"] for e in sv.lister(self.dossier)]
        self.assertEqual(noms, ["sauvegarde-02012026_0800.sql", "sauvegarde-01012026_0800.sql"])

    def test_creer_ecrit_le_dump_et_renvoie_le_chemin(self):
        def executer_ok(commande, stdout, stderr, env):
            stdout.write(b"-- dump mysql --\ninsert into histo ...;\n")
            self.assertIn("secret", env.get("MYSQL_PWD", ""))  # mot de passe transmis par env, pas par argv
            self.assertNotIn("secret", commande)  # jamais sur la ligne de commande
            return _FauxResultat(returncode=0)

        chemin = sv.creer(self.config, self.dossier, executer=executer_ok, horodatage=datetime(2026, 1, 5, 8, 7))
        self.assertEqual(os.path.basename(chemin), "sauvegarde-05012026_0807.sql")
        self.assertTrue(os.path.isfile(chemin))
        with open(chemin, "rb") as f:
            self.assertIn(b"dump mysql", f.read())

    def test_creer_leve_et_nettoie_si_mysqldump_absent(self):
        def executer_absent(*a, **kw):
            raise FileNotFoundError()

        with self.assertRaises(RuntimeError) as ctx:
            sv.creer(self.config, self.dossier, executer=executer_absent, horodatage=datetime(2026, 1, 5, 8, 7))
        self.assertIn("introuvable", str(ctx.exception))
        self.assertEqual(sv.lister(self.dossier), [])  # pas de fichier partiel laisse trainer

    def test_creer_leve_et_nettoie_si_mysqldump_echoue(self):
        def executer_echec(commande, stdout, stderr, env):
            stdout.write(b"contenu partiel")
            return _FauxResultat(returncode=1, stderr=b"Access denied for user")

        with self.assertRaises(RuntimeError) as ctx:
            sv.creer(self.config, self.dossier, executer=executer_echec, horodatage=datetime(2026, 1, 5, 8, 7))
        self.assertIn("Access denied", str(ctx.exception))
        self.assertEqual(sv.lister(self.dossier), [])

    def test_creer_leve_si_fichier_vide(self):
        def executer_vide(commande, stdout, stderr, env):
            return _FauxResultat(returncode=0)  # rien ecrit

        with self.assertRaises(RuntimeError) as ctx:
            sv.creer(self.config, self.dossier, executer=executer_vide, horodatage=datetime(2026, 1, 5, 8, 7))
        self.assertIn("vide", str(ctx.exception))


class AdminRoutesSmokeTests(unittest.TestCase):
    """Verifie que les routes Flask du Blueprint admin s'enchainent sans erreur."""

    def setUp(self):
        self.conn = build_test_db()
        import app as app_module
        self.app_module = app_module
        app_module.db.get_db = lambda: self.conn
        self.dossier_csv = tempfile.mkdtemp()
        app_module.app.config.update(TESTING=True, CSV_EXPORT_DIR=self.dossier_csv)
        self.client = app_module.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.dossier_csv, ignore_errors=True)

    def test_liste_magasins(self):
        r = self.client.get("/admin/magasins")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Magasin Dix", r.data)
        self.assertIn(b"Magasin Vingt", r.data)

    def test_creation_magasin_via_formulaire(self):
        r = self.client.post("/admin/magasins/nouveau", data={
            "code_ram": "BA", "magasin": "40", "nom": "Magasin Quarante",
            "partenaire": "", "lundi": "on", "mercredi": "on",
            "codart": ["0119000"], "libart": ["Pain"], "depot": ["03"], "codfour": ["02580004"],
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Magasin Quarante", r.data)

    def test_creation_magasin_invalide_reaffiche_le_formulaire(self):
        r = self.client.post("/admin/magasins/nouveau", data={
            "code_ram": "BA", "magasin": "50", "nom": "X",  # nom trop court
            "codart": [""], "libart": [""], "depot": [""], "codfour": [""],
        })
        self.assertEqual(r.status_code, 200)  # reaffiche le formulaire, pas de redirection
        self.assertIn("2 caracteres minimum".encode(), r.data)

    def test_modifier_magasin_existant(self):
        r = self.client.get("/admin/magasins/BA/10/modifier")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Magasin Dix", r.data)

        r = self.client.post("/admin/magasins/BA/10/modifier", data={
            "code_ram": "BA", "magasin": "10", "nom": "Magasin Dix Renomme",
            "partenaire": "", "lundi": "on",
            "codart": ["0119000"], "libart": ["Pain"], "depot": ["03"], "codfour": ["02580004"],
        }, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Magasin Dix Renomme", r.data)

    def test_supprimer_magasin(self):
        r = self.client.post("/admin/magasins/BA/20/supprimer", follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(b"Magasin Vingt", r.data)

    def test_parametres_fournisseurs_ajout_modif_suppression(self):
        r = self.client.get("/admin/parametres/fournisseurs")
        self.assertEqual(r.status_code, 200)

        r = self.client.post("/admin/parametres/fournisseurs/ajouter", data={
            "code": "02580099", "libelle": "Nouveau Fournisseur",
        }, follow_redirects=True)
        self.assertIn(b"Nouveau Fournisseur", r.data)

        r = self.client.post("/admin/parametres/fournisseurs/02580099/modifier", data={
            "libelle": "Fournisseur Renomme",
        }, follow_redirects=True)
        self.assertIn(b"Fournisseur Renomme", r.data)

        r = self.client.post("/admin/parametres/fournisseurs/02580099/supprimer", follow_redirects=True)
        self.assertNotIn(b"Fournisseur Renomme", r.data)

    def test_slug_inconnu_404(self):
        r = self.client.get("/admin/parametres/inconnu")
        self.assertEqual(r.status_code, 404)

    def test_epuration_affiche_le_formulaire_avec_une_date_par_defaut(self):
        r = self.client.get("/admin/epuration")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Date limite", r.data)

    def test_epuration_date_invalide_refusee(self):
        r = self.client.post("/admin/epuration", data={"date_limite": "pasunedate", "action": "calculer"})
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"invalide", r.data)

    def test_epuration_calcul_puis_confirmation_puis_suppression(self):
        _inserer_histo(self.conn, "2025-01-01")
        _inserer_histo(self.conn, "2026-06-01")  # recente, ne doit pas etre supprimee

        r = self.client.post("/admin/epuration", data={"date_limite": "01/01/2026", "action": "calculer"})
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"<strong>1</strong> ligne", r.data)

        r = self.client.post(
            "/admin/epuration", data={"date_limite": "01/01/2026", "action": "confirmer"}, follow_redirects=True
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("Epuration termin".encode(), r.data)

        self.assertEqual(se.compter(self.conn, "2027-01-01"), 1)  # ne reste que la ligne recente

    def test_epuration_sans_ligne_a_supprimer(self):
        r = self.client.post("/admin/epuration", data={"date_limite": "01/01/2020", "action": "calculer"})
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Aucune ligne", r.data)

    def test_sauvegarde_liste_les_fichiers_existants(self):
        with open(os.path.join(self.dossier_csv, "sauvegarde-01012026_0800.sql"), "w") as f:
            f.write("-- dump --")
        with open(os.path.join(self.dossier_csv, "notes.txt"), "w") as f:
            f.write("pas une sauvegarde")

        r = self.client.get("/admin/sauvegarde")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"sauvegarde-01012026_0800.sql", r.data)
        self.assertNotIn(b"notes.txt", r.data)

    def test_sauvegarde_creation_reussie(self):
        import services.sauvegarde as sauvegarde_module
        chemin_attendu = os.path.join(self.dossier_csv, "sauvegarde-05012026_0807.sql")
        with open(chemin_attendu, "w") as f:
            f.write("-- dump --")
        original = sauvegarde_module.creer
        sauvegarde_module.creer = lambda config, repertoire, **kw: chemin_attendu
        try:
            r = self.client.post("/admin/sauvegarde", follow_redirects=True)
        finally:
            sauvegarde_module.creer = original
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"sauvegarde-05012026_0807.sql", r.data)

    def test_sauvegarde_echec_affiche_le_message_d_erreur(self):
        import services.sauvegarde as sauvegarde_module

        def echoue(config, repertoire, **kw):
            raise RuntimeError("mysqldump est introuvable.")

        original = sauvegarde_module.creer
        sauvegarde_module.creer = echoue
        try:
            r = self.client.post("/admin/sauvegarde", follow_redirects=True)
        finally:
            sauvegarde_module.creer = original
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"mysqldump est introuvable", r.data)

    def test_sauvegarde_telechargement(self):
        chemin = os.path.join(self.dossier_csv, "sauvegarde-01012026_0800.sql")
        with open(chemin, "w") as f:
            f.write("-- contenu du dump --")

        r = self.client.get("/admin/sauvegarde/sauvegarde-01012026_0800.sql/telecharger")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"contenu du dump", r.data)
        r.close()  # libere le fichier envoye par send_from_directory (evite un ResourceWarning en test)

    def test_sauvegarde_telechargement_refuse_fichier_hors_motif(self):
        with open(os.path.join(self.dossier_csv, "notes.txt"), "w") as f:
            f.write("x")
        r = self.client.get("/admin/sauvegarde/notes.txt/telecharger")
        self.assertEqual(r.status_code, 404)

    def test_sauvegarde_telechargement_fichier_absent(self):
        r = self.client.get("/admin/sauvegarde/sauvegarde-01012026_0800.sql/telecharger")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
