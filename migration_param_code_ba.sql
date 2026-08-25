-- Migration : cloisonnement multi-site (CODE_BA) de la table `param`
-- (Fournisseurs / Articles / Types de ramasse), ajoutee suite au portage
-- web de ramasse10_sql.py.
--
-- A executer UNE SEULE FOIS sur votre base, APRES avoir deja execute
-- migration_login_multi_ba.sql (qui cree la table `user` et cloisonne
-- `histo`/`modeles`) :
--   mysql -u root -p yvallet_base < migration_param_code_ba.sql
-- ou via l'onglet "Executer une requete SQL" de phpMyAdmin.
--
-- Ce que fait ce script :
--   1) Ajoute une colonne code_ba a `param`.
--   2) Affecte code_ba = '58' aux enregistrements EXISTANTS de Fournisseurs
--      (code_type='F') et de Types de ramasse (code_type='T') - vos
--      donnees actuelles restent ainsi visibles une fois le cloisonnement
--      actif, comme pour histo/modeles.
--   3) Laisse code_ba a NULL pour les Articles (code_type='A') : par
--      exception explicitement demandee, les articles restent un
--      referentiel PARTAGE entre tous les sites, code_ba n'y est jamais
--      utilise.
--   4) Ajoute un index pour que les recherches par site restent rapides.
--
-- Prerequis : Create_yvallet_base_WithData.sql et migration_login_multi_ba.sql
-- ont deja ete executes (la table `param` et la colonne `code_ba` de
-- `histo`/`modeles` existent).

ALTER TABLE `param` ADD COLUMN `code_ba` varchar(10) NULL AFTER `code_type`;

UPDATE `param` SET `code_ba` = '58' WHERE `code_type` IN ('F', 'T');
-- Les articles (code_type = 'A') ne sont volontairement PAS mis a jour :
-- code_ba y reste NULL (referentiel partage entre tous les sites).

ALTER TABLE `param` ADD KEY `i_param_code_ba` (`code_ba`, `code_type`, `code`);

-- --------------------------------------------------------------------
-- Fin de la migration. Vous pouvez verifier avec :
--   SELECT code_ba, code_type, COUNT(*) FROM param GROUP BY code_ba, code_type;
-- (Fournisseurs et Types doivent tous etre sur code_ba = '58' pour
-- l'instant ; les Articles doivent tous avoir code_ba = NULL)
-- --------------------------------------------------------------------
