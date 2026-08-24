-- Migration : authentification (login/mot de passe) + cloisonnement
-- multi-site (CODE_BA), ajoutee suite au portage web de ramasse10_sql.py.
--
-- A executer UNE SEULE FOIS sur votre base existante, par exemple :
--   mysql -u root -p yvallet_base < migration_login_multi_ba.sql
-- ou via l'onglet "Executer une requete SQL" de phpMyAdmin.
--
-- Ce que fait ce script :
--   1) Cree la table `user` (comptes de connexion).
--   2) Ajoute une colonne code_ba a `histo` et `modeles`, pour que chaque
--      site (identifie par le CODE_BA de son compte utilisateur) ne voie
--      que ses propres donnees, meme si plusieurs sites partagent la
--      meme base a l'avenir.
--   3) Affecte code_ba = '58' a TOUTES les lignes deja existantes de
--      histo et modeles (vos donnees actuelles), pour qu'elles restent
--      visibles une fois le cloisonnement actif.
--   4) Reindexe histo et modeles avec code_ba en tete de leurs index
--      existants (i_histo, i_modeles), pour que les recherches par site
--      restent rapides sans avoir besoin d'index supplementaires.
--
-- Prerequis : le fichier Create_yvallet_base_WithData.sql a deja ete
-- importe (les tables histo/modeles/param existent).

-- --------------------------------------------------------------------
-- 1) Table des comptes utilisateur
-- --------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `user` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `login` varchar(120) NOT NULL,
  `mot_de_passe` varchar(255) NOT NULL,
  `code_ba` varchar(10) NOT NULL,
  `nom_ba` varchar(60) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `i_user_login` (`login`),
  KEY `i_user_code_ba` (`code_ba`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Le compte administrateur par defaut (yvmaison@free.fr / admin) est
-- cree automatiquement par l'application au demarrage si la table `user`
-- existe et qu'aucun compte avec ce login n'y figure deja - voir
-- services/utilisateurs.py (assurer_admin_par_defaut). Pas besoin de
-- l'inserer ici a la main. PENSEZ A CHANGER CE MOT DE PASSE des la
-- premiere connexion (menu Utilisateurs, reserve au CODE_BA '00').

-- --------------------------------------------------------------------
-- 2) Cloisonnement de l'historique de ramasse (`histo`) par site
-- --------------------------------------------------------------------

ALTER TABLE `histo` ADD COLUMN `code_ba` varchar(10) NOT NULL DEFAULT '58' AFTER `code_ram`;

-- Reindexation : code_ba en tete pour que "WHERE code_ba = ... AND
-- code_ram = ..." (le cas de toutes les requetes de l'application)
-- utilise l'index efficacement, sans avoir besoin d'un index separe.
ALTER TABLE `histo` DROP INDEX `i_histo`;
ALTER TABLE `histo` ADD UNIQUE KEY `i_histo` (`code_ba`, `code_ram`, `date_ram`, `magasin`, `nolig`);

-- Le DEFAULT '58' n'a servi qu'a remplir les lignes deja existantes lors
-- du ADD COLUMN ci-dessus ; on le retire ensuite pour qu'un futur INSERT
-- qui oublierait de preciser code_ba echoue au lieu de silencieusement
-- rattacher la ligne au site 58.
ALTER TABLE `histo` ALTER COLUMN `code_ba` DROP DEFAULT;

-- --------------------------------------------------------------------
-- 3) Cloisonnement des modeles de magasin (`modeles`) par site
-- --------------------------------------------------------------------

ALTER TABLE `modeles` ADD COLUMN `code_ba` varchar(10) NOT NULL DEFAULT '58' AFTER `code_ram`;

ALTER TABLE `modeles` DROP INDEX `i_modeles`;
ALTER TABLE `modeles` ADD KEY `i_modeles` (`code_ba`, `code_ram`, `magasin`, `nolig`);

ALTER TABLE `modeles` ALTER COLUMN `code_ba` DROP DEFAULT;

-- --------------------------------------------------------------------
-- Fin de la migration. Vous pouvez verifier avec :
--   SELECT code_ba, COUNT(*) FROM histo GROUP BY code_ba;
--   SELECT code_ba, COUNT(*) FROM modeles GROUP BY code_ba;
-- (tout doit etre sur '58' pour l'instant)
-- --------------------------------------------------------------------
