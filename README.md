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
  (code article, designation, depot, fournisseur).
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

## Ce qui n'est PAS encore dans cette version (a faire dans un 2e temps, si besoin)

Sauvegarde et impression d'etiquettes / bon de reception PDF (fonctions de
`outils.py` non liees a la saisie journaliere ni a la gestion des
magasins/fournisseurs/articles/types/historique : FTP/SFTP, `PDFBR`,
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

## Log des erreurs d'execution

Il y a deux niveaux :

- **Console** : tant que vous lancez l'appli avec `python3 app.py`, chaque
  requete et chaque erreur s'affichent dans le terminal ; et comme
  `debug=True`, une erreur non geree affiche aussi sa pile d'appels
  directement dans le navigateur (pratique pendant les tests, a desactiver
  avant un usage en production - voir plus bas).
- **Fichier persistant** : `logs/app.log`, a cote de `app.py` (cree
  automatiquement au demarrage, avec rotation - 5 fichiers de 1 Mo max).
  C'est l'equivalent du `LOG.log` de l'original (ecrit par `get_logger()`
  dans `outils.py`). Toute saisie refusee (quantite/rebut invalide, rebut >
  quantite...) y est journalisee avec le magasin et la date concernes,
  ainsi que toute erreur non geree.

Pour un usage en production (plusieurs postes), pensez a passer
`debug=False` dans `app.run(...)` (fin de `app.py`) ou, mieux, a lancer
l'appli avec un vrai serveur WSGI (voir plus bas) : le mode debug de Flask
ne doit pas rester actif face a des utilisateurs autres que vous.

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
ajout/modification/suppression de fournisseurs/articles/types, et
epuration de l'historique (calcul du nombre de lignes concernees,
confirmation, suppression effective, absence de filtre par type de
ramasse). Comme cet environnement de developpement n'a pas acces a un vrai
serveur MySQL, les tests utilisent une base sqlite3 en memoire qui rejoue
exactement les memes requetes SQL (`tests/db_shim.py`) :

```bash
python3 tests/test_workflow.py
python3 tests/test_admin.py
```

Les 50 tests (14 + 36) passent. Avant la mise en production, faites tout de
meme un essai manuel complet avec votre vraie base MySQL locale (le
connecteur MySQL n'a pas pu etre installe dans cet environnement de
developpement, faute d'acces reseau — a verifier avec
`pip install -r requirements.txt` chez vous).

## Differences volontaires par rapport a l'original

- **Multi-utilisateurs** : l'original gardait tout en variables globales
  Python (une seule connexion, un seul "magasin courant" pour tout le
  monde). La version web garde le type de ramasse / la date / le magasin
  courant dans la session du navigateur de chaque utilisateur : plusieurs
  postes peuvent saisir des magasins differents en meme temps sans se
  marcher dessus.
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
