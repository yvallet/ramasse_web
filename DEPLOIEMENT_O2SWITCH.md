# Mise en production sur o2switch (hebergement mutualise)

Ce document decrit le deploiement de `ramasse_web` sur o2switch (cPanel +
Phusion Passenger), en gardant la branche `main` comme version locale/reseau
inchangee. Le code deploye vient de la branche `deploy` du meme depot GitHub.

Voir aussi le README.md (fonctionnement general de l'application) et
`.env.example` (liste complete des variables).

## 1. Sous-domaine

Dans cPanel, creez un sous-domaine (ex. `ramasse.mondomaine.fr`) pointant
vers un dossier dedie (ex. `~/ramasse_web`).

## 2. Application Python (cPanel "Setup Python App")

- **Version Python** : la plus haute proposee, >= 3.9 (l'application n'a pas
  de dependance a une version recente specifique). Verifiez avec
  `python --version` dans le virtualenv cree par cPanel une fois l'app
  enregistree.
- **Application root** : le dossier du depot (ex. `ramasse_web`).
- **Application URL** : le sous-domaine cree a l'etape 1.
- **Application startup file** : `passenger_wsgi.py`
- **Application Entry point** : `application`

## 3. Recuperer le code

Deux options :

- cPanel **Git Version Control** : "Create", URL du depot GitHub
  (`https://github.com/yvallet/ramasse_web.git`), branche `deploy`.
- ou en SSH : `git clone -b deploy https://github.com/yvallet/ramasse_web.git`

## 4. Fichier `.env` de production

Cree **directement sur le serveur** (jamais commite), a la racine de
l'application, a partir de `.env.example` :

```
RAMASSE_ENV=production
SECRET_KEY=<sortie de: python -c "import secrets; print(secrets.token_hex(32))">
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DB=<compte>_yvallet_base
MYSQL_USER=<compte>_ramasse
MYSQL_PASSWORD=<mot de passe cPanel>
CSV_EXPORT_DIR=/home/<compte>/ramasse_export
MYSQLDUMP_PATH=<voir etape 8>
SMTP_HOST=mail.mondomaine.fr
SMTP_PORT=587
SMTP_USER=ramasse@mondomaine.fr
SMTP_PASSWORD=<mot de passe de cette boite>
SMTP_FROM=ramasse@mondomaine.fr
APP_BASE_URL=https://ramasse.mondomaine.fr
ADMIN_INITIAL_PASSWORD=<mot de passe temporaire, a retirer apres coup>
```

En production, l'application refuse de demarrer si `SECRET_KEY` ou
`MYSQL_PASSWORD` sont absents (voir `app.py`, `_verifier_secrets_prod`) -
c'est volontaire.

## 5. Dependances

Dans le virtualenv cree par cPanel pour l'application (bouton "Run pip
install" de l'interface, ou en SSH) :

```bash
source /home/<compte>/virtualenv/ramasse_web/<version>/bin/activate
pip install -r requirements.txt
```

## 6. Base de donnees MySQL

Dans cPanel : creer une base et un utilisateur MySQL (prefixes automatiquement
par le nom du compte), puis via phpMyAdmin :

1. Si base neuve : importer `Create_yvallet_base_WithData.sql`.
2. **Dans l'ordre**, une seule fois chacun :
   - `migration_login_multi_ba.sql`
   - `migration_param_code_ba.sql`

## 7. Repertoire d'export

```bash
mkdir -p ~/ramasse_export
```
(doit correspondre a `CSV_EXPORT_DIR` dans le `.env`)

## 8. `mysqldump` (fonction Sauvegarde, reservee a l'administrateur)

En SSH :
```bash
which mysqldump
```
Renseignez le chemin trouve dans `MYSQLDUMP_PATH` du `.env` si different de
`mysqldump` seul.

## 9. HTTPS

Activez le certificat Let's Encrypt gratuit (cPanel "SSL/TLS Status") pour le
sous-domaine, puis "Force HTTPS Redirect".

## 10. Demarrer / redemarrer l'application

Bouton "Restart" dans "Setup Python App", ou :
```bash
touch /home/<compte>/ramasse_web/tmp/restart.txt
```

## 11. Premiere connexion

1. Se connecter avec `yvmaison@free.fr` / `ADMIN_INITIAL_PASSWORD`.
2. Changer immediatement son mot de passe (menu Utilisateurs).
3. Retirer `ADMIN_INITIAL_PASSWORD` du `.env` (plus necessaire).
4. Creer un compte par site (CODE_BA) depuis le menu Utilisateurs.

## 12. Tests de fumee

- Connexion / deconnexion.
- Un cycle de saisie journaliere complet (jusqu'a l'export CSV).
- Une sauvegarde SQL (Administration > Sauvegarde), telechargement du
  fichier produit.
- Un cycle complet "mot de passe oublie" : demande, reception effective de
  l'e-mail, lien valide, nouveau mot de passe pris en compte, lien
  desormais invalide.
- Verifier dans les outils de developpement du navigateur : cookie de
  session marque `Secure`, en-tete `Strict-Transport-Security` present,
  redirection HTTP -> HTTPS effective.
