# Ramasse journaliere - version web (Flask)

Portage web du programme tkinter `ramasse10_sql.py`, en conservant la meme
base MySQL (`Create_yvallet_base_WithData.sql`) et la meme logique
metier. Deux lots ont ete livres jusqu'ici :

**Lot 1 (MVP) - ecran de saisie journaliere :**

- Page 1 : choix du type de ramasse (BA / BOUL / ELOI / CLAM...) et de la
  date de tournee, avec la meme suggestion automatique de "prochaine date
  ouvree" que l'original.
- Page 2 : saisie des quantites/rebuts par magasin, navigation
  Suivant/Precedent, ajout d'un magasin non prevu ce jour-la, controle
  "rebut > quantite" bloquant, confirmation si un magasin est laisse a
  zero, export des 2 CSV VIF (reception + rebuts) au meme format que
  l'original, sortie sans export avec purge de la journee si tout est a
  zero.

**Lot 2 - ecrans d'administration** (`admin.py`), accessibles depuis le
menu en haut de chaque page :

- **Gestion des magasins** (equivalent de `magasin()` / `valid_mag()` /
  `sup_mag()` de l'original) : liste des magasins/modeles existants,
  creation, modification et suppression - nom, partenaire (COMERSO/PHENIX),
  rebut possible, jours de collecte, et la liste des articles collectes
  (code article, designation, depot, fournisseur). **Difference volontaire :
  le code article et le code fournisseur sont desormais choisis dans une
  liste deroulante** (respectivement la liste des Articles, partagee entre
  tous les sites, et la liste des Fournisseurs du site connecte) plutot que
  saisis en texte libre comme dans l'original - la designation se
  pre-remplit avec le libelle de l'article choisi (modifiable ensuite).
- **Gestion des fournisseurs**, **Gestion des articles** et **Gestion des
  types de ramasse** (equivalent de l'ecran generique `fenetre9` /
  `charger_clients()` / `ajout_cli()` / `sup_cli()` de l'original, reutilise
  3 fois) : liste, ajout et suppression de codes ; **la modification, qui
  n'existait pas dans l'original** (`modif_cli()` etait un bouton non
  implemente), a ete ajoutee.

**Lot 3 - epuration de l'historique** (equivalent de `fenetre10` /
`epuration()` / `valider_epur()` de l'original) : purge definitive de la
table `histo` de toutes les lignes anterieures a une date choisie (par
defaut, aujourd'hui - 30 jours, comme l'original) - tous types de ramasse
et tous magasins confondus, exactement comme dans l'original (la
suppression n'est pas filtree par type de ramasse). Difference volontaire :
l'ecran annonce d'abord le nombre de lignes concernees et demande une
confirmation explicite avant de supprimer, alors que l'original supprimait
directement au clic sur "Valider" sans annoncer ce nombre au prealable -
une purge etant irreversible et potentiellement large, une confirmation
minimale semblait justifiee.

**Lot 4 - sauvegarde SQL de la base** (`services/sauvegarde.py`) :
**fonctionnalite absente de l'original** - `ramasse10_sql.py` ne fait
aucune sauvegarde automatisee de la base (seul l'export CSV VIF existe,
qui ne couvre que les lignes de la journee, pas la base entiere). L'ecran
"Sauvegarde" lance un dump SQL complet (structure + toutes les donnees,
via `mysqldump`), enregistre dans le meme repertoire que les exports CSV
(`CSV_EXPORT_DIR`), sous le nom `sauvegarde-jjmmaaaa_hhmm.sql` ; la liste
des sauvegardes existantes s'affiche avec leur date et leur taille, avec
un lien de telechargement pour chacune. Le mot de passe MySQL est transmis
a `mysqldump` par variable d'environnement (jamais sur la ligne de
commande) pour ne pas apparaitre dans la liste des processus du systeme.

**Prerequis** : `mysqldump` doit etre installe sur la machine qui fait
tourner l'application (fourni avec MySQL Server / MySQL Workbench sous
Windows) et accessible dans le PATH, ou son chemin complet renseigne dans
`.env` via `MYSQLDUMP_PATH` (voir `.env.example`).

**Lot 5 - authentification et multi-site** (`auth.py`, `services/
utilisateurs.py`) : **fonctionnalite absente de l'original** -
`ramasse10_sql.py` etait un programme desktop mono-poste, sans notion de
compte utilisateur. Pour permettre d'heberger l'application sur un serveur
partage entre plusieurs sites ("BA"), toute l'application exige desormais
d'etre connecte :

- Une table `user` (login = adresse mail, mot de passe hashe, CODE_BA,
  nom_BA) associe chaque compte a un site. **Le CODE_BA du compte connecte
  remplace desormais le CODE_BA jusque-la fixe dans `.env`** : il n'existe
  plus de reglage global au serveur, chaque connexion determine les
  magasins et l'historique visibles.
- Convention : **CODE_BA = '00' identifie l'administrateur**, seul autorise
  a acceder au menu "Utilisateurs" (creation/modification/suppression des
  comptes) ainsi qu'a l'ecran "Sauvegarde" (le dump SQL contient les
  donnees de TOUS les sites). Un administrateur n'a pas de donnees de
  ramasse propres.
- Un premier compte administrateur est cree automatiquement au demarrage
  (`yvmaison@free.fr` / `admin` / CODE_BA `00`) s'il n'existe pas encore -
  **a changer immediatement** apres la premiere connexion (menu
  Utilisateurs). Les comptes des sites sont ensuite crees par
  l'administrateur depuis cet ecran.
- "Mot de passe oublie" : l'utilisateur saisit son login, recoit (si le
  compte existe) un e-mail avec un lien de reinitialisation signe, valable
  1 heure (`auth.py`, `services/mail.py`). Sans serveur SMTP configure
  (`SMTP_HOST` absent du `.env` - le cas par defaut en local), le lien
  n'est pas perdu : il est journalise dans `logs/app.log`. Remplace
  l'ancienne version simplifiee (login + nouveau mot de passe sur le meme
  ecran, sans verification) qui laissait quiconque connaissant l'adresse
  d'un compte reinitialiser son mot de passe - voir "Mise en production"
  plus bas.
- Cloisonnement des donnees : les tables `histo`, `modeles` et `param`
  portent desormais une colonne `code_ba`, et toute lecture/ecriture y est
  systematiquement filtree par le CODE_BA de l'utilisateur connecte -
  jamais une valeur choisie par le navigateur (voir `services/ramasse.py`,
  `services/magasins.py`, `services/epuration.py`, `services/
  parametres.py`). Sur la table `param` : **Fournisseurs et Types de
  ramasse sont desormais propres a chaque site** (chaque site cree/gere sa
  propre liste, invisible des autres) ; **seuls les Articles restent un
  referentiel partage** entre tous les sites (exception explicitement
  demandee - `code_ba` reste a NULL pour ces lignes et n'est jamais pris en
  compte).
- **Migration de base necessaire, en 2 scripts** : executez, dans l'ordre,
  `migration_login_multi_ba.sql` puis `migration_param_code_ba.sql` sur
  votre base MySQL existante (une seule fois chacun) avant de deployer
  cette version :
  - le premier cree la table `user` et ajoute la colonne `code_ba` aux
    tables `histo`/`modeles` (leurs lignes existantes sont rattachees a
    CODE_BA = '58', nom_BA = 'BA 58') ;
  - le second ajoute la colonne `code_ba` a `param`, rattache les
    Fournisseurs et Types de ramasse existants a CODE_BA = '58', et laisse
    les Articles a NULL (referentiel partage).
  Rien de tout cela n'est perdu : c'est uniquement le cloisonnement qui
  devient actif, sur des donnees deja en place.

## Ce qui n'est PAS encore dans cette version (a faire dans un 2e temps, si besoin)

Impression d'etiquettes et de bon de reception PDF (fonctions de
`outils.py` non liees a la saisie journaliere ni a la gestion des
magasins/fournisseurs/articles/types/historique/sauvegarde : `PDFBR`,
`etiquette2` - elles n'ont pas ete reprises pour l'instant).

## Installation

```bash
cd ramasse_web
python3 -m venv venv
source venv/bin/activate          # Windows : venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env            # Windows ; sous Linux/Mac : cp .env.example .env
# éditer .env : mot de passe MySQL, dossier d'export CSV, etc.
```

Le schema MySQL est le meme que celui de l'appli desktop : si la base
`yvallet_base` existe deja (celle utilisee par ramasse10_sql.py), rien a
importer. Sinon, importer `Create_yvallet_base_WithData.sql` comme avant.

Puis, dans tous les cas (base neuve ou existante), executer les 2 scripts
de migration ci-dessous, **dans l'ordre, chacun une seule fois**, pour
ajouter l'authentification multi-site et le cloisonnement de `param` (voir
le Lot 5 plus haut) :

```bash
mysql -u root -p yvallet_base < migration_login_multi_ba.sql
mysql -u root -p yvallet_base < migration_param_code_ba.sql
```

Au premier demarrage de l'application apres ces migrations, un compte
administrateur par defaut est cree automatiquement (`yvmaison@free.fr` /
CODE_BA `00`) - connectez-vous et changez son mot de passe tout de suite
(menu Utilisateurs), puis creez un compte par site. En local
(`RAMASSE_ENV` non defini), son mot de passe est `admin` par defaut ; en
production, voir "Mise en production" plus bas (`ADMIN_INITIAL_PASSWORD`).

## Log des erreurs d'execution

Il y a deux niveaux :

- **Console** : tant que vous lancez l'appli avec `python3 app.py` en local
  (`RAMASSE_ENV` non defini ou `local`), chaque requete et chaque erreur
  s'affichent dans le terminal, et le mode debug de Flask affiche aussi la
  pile d'appels directement dans le navigateur en cas d'erreur (pratique
  pendant les tests). Ce mode debug se desactive automatiquement des que
  `RAMASSE_ENV=production` (voir "Mise en production" plus bas) - il ne
  doit jamais rester actif face a des utilisateurs autres que vous.
- **Fichier persistant** : `logs/app.log`, a cote de `app.py` (cree
  automatiquement au demarrage, avec rotation - 5 fichiers de 1 Mo max).
  C'est l'equivalent du `LOG.log` de l'original (ecrit par `get_logger()`
  dans `outils.py`). Toute saisie refusee (quantite/rebut invalide, rebut >
  quantite...) y est journalisee avec le magasin et la date concernes,
  ainsi que toute erreur non geree.

## Lancer l'application

```bash
python3 app.py
```

Puis ouvrir http://localhost:5000 dans un navigateur. Pour un usage par
plusieurs postes en meme temps (magasins/utilisateurs differents), lancer
avec un vrai serveur WSGI (ex: `waitress` sur Windows, `gunicorn` sur
Linux) plutot que le serveur de developpement Flask, et heberger l'appli
sur un poste/serveur accessible depuis le reseau local des autres postes.

## Tests

Un jeu de tests automatiques verifie la logique portee (creation de la
journee selon le jour de semaine, navigation, controle rebut/quantite,
cumuls, export CSV, suggestion de date...) ainsi que l'enchainement complet
des routes Flask, pour la saisie journaliere (`tests/test_workflow.py`) et
pour les ecrans d'administration (`tests/test_admin.py`) : validation des
formulaires magasin (article/fournisseur inconnu, doublon de couple
type+magasin...), creation/modification/suppression d'un magasin,
ajout/modification/suppression de fournisseurs/articles/types,
epuration de l'historique (calcul du nombre de lignes concernees,
confirmation, suppression effective, absence de filtre par type de
ramasse), sauvegarde SQL (nom de fichier genere, liste des sauvegardes,
gestion des echecs mysqldump, mot de passe jamais expose sur la ligne de
commande, telechargement), et authentification multi-site (creation/
modification/suppression de compte, connexion/deconnexion, "mot de passe
oublie", reservation du menu Utilisateurs et de la Sauvegarde a
l'administrateur, cloisonnement des donnees d'un site a l'autre pour les
magasins/l'historique/les fournisseurs/les types de ramasse, et le
caractere bien partage entre tous les sites des articles), ainsi que le
durcissement pour une exposition sur Internet (protection CSRF, en-tetes de
securite, anti-force-brute, cycle complet de reinitialisation de mot de
passe par lien e-mail signe, compte administrateur initial parametrable -
voir "Mise en production" plus bas). Comme cet environnement de
developpement n'a acces
ni a un vrai serveur MySQL ni a `mysqldump`, les tests utilisent une base
sqlite3 en memoire qui rejoue exactement les memes requetes SQL
(`tests/db_shim.py`), et un `mysqldump` simule pour la sauvegarde :

```bash
python3 tests/test_workflow.py
python3 tests/test_admin.py
```

Les 108 tests (17 + 91) passent. Avant la mise en production, faites tout de
meme un essai manuel complet avec votre vraie base MySQL locale et un vrai
`mysqldump` (le connecteur MySQL n'a pas pu etre installe dans cet
environnement de developpement, faute d'acces reseau — a verifier avec
`pip install -r requirements.txt` chez vous).

## Mise en production (serveur expose sur Internet)

L'application est prete a etre exposee sur Internet (ex. hebergement
mutualise o2switch) via la variable `RAMASSE_ENV=production` : cookies de
session securises, mode debug desactive, protection CSRF (Flask-WTF),
anti-force-brute sur la connexion et le mot de passe oublie, en-tetes de
securite HTTP, reinitialisation de mot de passe par un vrai lien e-mail
signe (au lieu du flux simplifie sans verification utilise en local), et
compte administrateur initial parametrable via `ADMIN_INITIAL_PASSWORD`
(aucun compte "admin"/"admin" cree par defaut en production). Voir toutes
les variables dans `.env.example` et le guide pas-a-pas complet dans
[DEPLOIEMENT_O2SWITCH.md](DEPLOIEMENT_O2SWITCH.md).

Cette version deploiement vit sur la branche `deploy` du depot : la branche
`main` reste la version reseau local, inchangee.

## Differences volontaires par rapport a l'original

- **Multi-utilisateurs et multi-site** : l'original gardait tout en
  variables globales Python (une seule connexion, un seul "magasin
  courant", un seul CODE_BA pour tout le monde). La version web garde le
  type de ramasse / la date / le magasin courant dans la session de chaque
  utilisateur connecte, et chaque compte est desormais rattache a un
  CODE_BA (voir le Lot 5 plus haut) : plusieurs sites peuvent partager le
  meme serveur sans jamais voir les magasins ou l'historique les uns des
  autres, et plusieurs postes d'un meme site peuvent saisir des magasins
  differents en meme temps sans se marcher dessus.
- **Ecran de saisie - nom du type de ramasse affiche** : `detail.html` et
  `confirmer_fin.html` affichent desormais le libelle du type de ramasse
  (ex: "Ramasse BA"), et non plus son code brut ("BA") comme auparavant.
- **Ecran de saisie par magasin - impossible de quitter par le menu** :
  corrige un vrai piege signale par l'utilisateur - la saisie du magasin
  affiche n'est enregistree qu'au clic sur Enregistrer/Suivant/Precedent/
  Terminer, donc cliquer sur un lien du menu (Magasins, Fournisseurs...) ou
  sur "Se deconnecter" pendant la saisie d'un magasin faisait perdre la
  ligne en cours sans avertissement. Le menu, le lien "Ramasse journaliere"
  et "Se deconnecter" sont desormais masques tant que l'ecran de saisie par
  magasin (`/detail`) est affiche : seuls les boutons "Quitter" et
  "Terminer la journee" permettent d'en sortir. Les autres ecrans (choix du
  type/date, confirmation de fin de journee, administration) ne sont pas
  concernes, rien n'y est modifiable sans passer par un bouton "Enregistrer".
- **Protection contre la modification d'une ligne d'un autre site** :
  fonctionnalite absente de l'original (qui n'avait pas cette notion).
  L'enregistrement d'une ligne de saisie (`save_lines`) verifie desormais
  que son identifiant appartient bien au CODE_BA de l'utilisateur connecte
  avant de la mettre a jour - sans ce controle, un identifiant de ligne
  modifie dans le formulaire aurait pu, en theorie, mettre a jour la ligne
  d'un AUTRE site (les identifiants sont de simples entiers auto-
  incrementes, partages entre tous les sites).
- **Requetes SQL parametrees** : l'original construisait ses requetes par
  concaténation de chaines (`"... where code_ram = " + quot + wc + quot`).
  Le portage utilise des parametres (`%s`) partout : meme resultat, sans le
  risque d'injection SQL de la version d'origine.
- **Dimanche** : l'original ne gerait pas explicitement le dimanche
  (aucune branche dans `creer_histo`), ce qui produisait un ecran 2 vide
  avec un message "Pas de suivant, fin de liste". La version web bloque
  directement sur l'ecran 1 avec un message clair.
- **Confirmation "magasin vide"** : l'original demandait une confirmation
  magasin par magasin lors de la validation finale. Le portage les
  regroupe en un seul ecran de confirmation listant tous les magasins
  vides d'un coup (plus rapide a l'usage, meme information).
- **Encodage des CSV** : l'original ouvrait les fichiers avec
  `encoding='ANSI'` (alias Windows). Le portage utilise `cp1252`
  (Windows-1252, l'encodage reel derriere "ANSI" sur un Windows francais)
  avec repli sur un caractere de remplacement si un caractere n'est pas
  representable — a verifier avec un import VIF reel.
- **Gestion des magasins - type de ramasse en liste deroulante** : le
  code_ram est desormais choisi parmi les types deja crees (via Gestion des
  types de ramasse), plutot que saisi en texte libre comme dans l'original
  - qui laissait `veriftype()` inutilisee sur ce champ et permettait de
  creer un magasin avec un type inexistant.
- **Gestion des magasins - doublon detecte a la creation** : creer un
  magasin avec un couple (type, code magasin) deja existant est desormais
  refuse avec un message ; l'original inserait des lignes en double sans
  le signaler.
- **Gestion des magasins - champ fournisseur d'en-tete retire** : ce champ
  (`wcodfour`/`zcodfour` dans l'original) etait valide mais jamais utilise
  a l'enregistrement (chaque ligne d'article a son propre fournisseur) -
  c'etait un champ mort, non repris.
- **Gestion des magasins - plus de plafond a 10 lignes** : le formulaire
  web permet d'ajouter/retirer des lignes d'article librement, alors que
  l'original limitait la fiche magasin a 10 articles (dix couples de
  champs `qte1`..`qte10` cables en dur dans l'interface tkinter).
- **Gestion des fournisseurs/articles/types - modification ajoutee** :
  l'original ne permettait que d'ajouter ou de supprimer un code
  (`modif_cli()` etait un bouton non implemente, il fallait supprimer puis
  recreer pour changer un libelle). Le portage ajoute une vraie
  modification.

## Journal des corrections

- **La colonne "Total jour article" se met desormais a jour a chaque
  frappe** (quantite ou rebut), en tenant compte de la saisie en cours de
  tout le magasin affiche a l'ecran - pas seulement de ce qui est deja
  enregistre en base. C'est l'equivalent des fonctions `after_qteN` /
  `after_rebutN` de l'original, qui recalculaient ce total a chaque sortie
  de champ via `cumul2()`. Le serveur envoie desormais, avec la page, le
  total deja enregistre pour tous les AUTRES magasins (`totaux_hors_magasin`
  dans `services/ramasse.py`) ; le navigateur y ajoute en direct, sans
  recharger la page, la saisie du magasin en cours (`static/detail.js`).

- **Une quantite ou un rebut mal saisi ("ABCD", "100..200"...) etait
  silencieusement enregistre comme 0**, sans aucun message - contrairement
  a l'original, qui affichait "Quantite invalide" via `anomalie()`. En
  cause : `_lire_lignes_soumises()` (`app.py`) rattrapait l'erreur de
  conversion et remplacait la valeur par 0 sans le signaler. Desormais,
  une valeur non numerique est refusee avec un message clair et RIEN n'est
  enregistre pour cette sauvegarde (`app.py`, fonction `_parse_nombre`).
  Le champ concerne s'affiche aussi en rouge des la frappe, cote
  navigateur (`static/detail.js`).
- **La touche ENTREE pouvait declencher le mauvais bouton** (par ex.
  revenir au magasin precedent au lieu d'enregistrer), un comportement du
  aux plusieurs boutons de validation presents dans le meme formulaire
  HTML : le navigateur soumet celui qui vient en premier et n'est pas
  desactive. ENTREE passe desormais au champ suivant, comme la
  tabulation ; seul un clic explicite sur un bouton (ou ENTREE une fois
  focus dessus) declenche une action.
- Un **log d'execution persistant** (`logs/app.log`, avec rotation) a ete
  ajoute - il n'y avait auparavant que la console. Voir la section
  "Log des erreurs d'execution" plus haut.

## Fichiers manquants restitues par vos soins

`outils.py` et `param_ramasse.txt` ont ete fournis pendant l'echange pour
completer l'analyse. Seules les fonctions de dates de `outils.py`
(`date_jour`, `amj`, `jma`, `verif_date`) sont utilisees par cet ecran ;
elles sont reprises dans `services/dateutils.py`. Le reste de
`outils.py` (FTP/SFTP, etiquettes, PDF bon de reception) sert a d'autres
ecrans du programme desktop, non couverts par ce MVP.

Le dossier d'icones (`repertoire_images_sql` dans `param_ramasse.txt`) n'a
pas ete fourni : ce portage web n'en a pas besoin (boutons HTML/CSS
standards a la place des images de boutons tkinter).
