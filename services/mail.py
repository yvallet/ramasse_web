# coding: utf8
"""
Envoi d'e-mail (stdlib uniquement, aucune dependance supplementaire) -
utilise pour le lien de reinitialisation de mot de passe (voir auth.py).
Fonctionnalite absente de l'original (application desktop mono-poste).

Deux transports (MAIL_TRANSPORT, voir config.py) :
- "smtp" (par defaut) : connexion reseau au serveur SMTP (SMTP_HOST/PORT/
  USER/PASSWORD/STARTTLS).
- "sendmail" : remise locale au MTA du serveur via le binaire `sendmail`
  (comme PHP mail()), sans connexion reseau. A utiliser si l'hebergeur
  bloque les connexions sortantes du process applicatif vers le serveur
  SMTP alors qu'une session SSH classique y arrive sans probleme (constate
  sur o2switch : timeout systematique depuis l'app Passenger, alors que le
  meme SMTP_HOST/port repond immediatement depuis un shell SSH) - sendmail
  est une remise locale par pipe, pas une connexion reseau, donc hors de
  portee de ce type de restriction.

Si SMTP_HOST n'est pas configure (mode smtp) : envoyer() n'echoue pas,
elle journalise le message en entier via le logger fourni. C'est le mode
attendu en local/developpement, ou aucun serveur SMTP n'est disponible - le
lien de reinitialisation se lit alors dans logs/app.log.
"""
import smtplib
import subprocess
from email.message import EmailMessage


def envoyer(config, destinataire, sujet, corps_texte, logger=None, executer=subprocess.run):
    """
    Envoie un e-mail texte simple. `config` : mapping donnant acces a
    MAIL_TRANSPORT, MAIL_SENDMAIL_PATH, et SMTP_HOST/PORT/USER/PASSWORD/
    FROM/STARTTLS (app.config convient tel quel).

    `executer` : injectable pour les tests (transport "sendmail"
    uniquement), meme signature que subprocess.run.

    Sans SMTP_HOST configure (transport "smtp", par defaut) : ne leve
    jamais, journalise le contenu complet (sujet + corps, donc le lien)
    via `logger` si fourni, sinon ne fait rien - c'est a l'appelant de
    fournir un logger en production pour ne pas perdre silencieusement un
    envoi.

    Leve RuntimeError si l'envoi est configure (SMTP_HOST, ou transport
    sendmail) mais echoue : l'appelant decide quoi en faire (ex. message
    d'erreur generique a l'utilisateur).
    """
    message = EmailMessage()
    message["Subject"] = sujet
    message["From"] = config.get("SMTP_FROM") or config.get("SMTP_USER") or "no-reply@localhost"
    message["To"] = destinataire
    message.set_content(corps_texte)

    transport = (config.get("MAIL_TRANSPORT") or "smtp").strip().lower()
    if transport == "sendmail":
        _envoyer_par_sendmail(config, message, executer)
        return True

    hote = config.get("SMTP_HOST")
    if not hote:
        if logger is not None:
            logger.warning(
                "SMTP non configure - e-mail non envoye a %s. Sujet : %s\n%s",
                destinataire, sujet, corps_texte,
            )
        return False

    port = int(config.get("SMTP_PORT") or 587)
    # Port 465 = TLS implicite des la connexion (SMTPS) : il faut
    # SMTP_SSL, pas SMTP + starttls() (qui suppose une connexion en clair
    # suivie d'une commande STARTTLS - le protocole du port 587). Utiliser
    # SMTP + starttls() sur le port 465 echoue silencieusement ou se bloque.
    classe_smtp = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
    try:
        with classe_smtp(hote, port, timeout=10) as serveur:
            if port != 465 and config.get("SMTP_STARTTLS", True):
                serveur.starttls()
            if config.get("SMTP_USER"):
                serveur.login(config["SMTP_USER"], config.get("SMTP_PASSWORD") or "")
            serveur.send_message(message)
    except (OSError, smtplib.SMTPException) as e:
        raise RuntimeError("Envoi de l'e-mail a %s echoue : %s" % (destinataire, e))

    return True


def _envoyer_par_sendmail(config, message, executer):
    """Remise locale via le binaire sendmail (voir docstring du module)."""
    chemin = config.get("MAIL_SENDMAIL_PATH") or "/usr/sbin/sendmail"
    try:
        resultat = executer(
            [chemin, "-t", "-i"],
            input=message.as_bytes(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise RuntimeError("sendmail (%s) introuvable ou en echec : %s" % (chemin, e))

    if resultat.returncode != 0:
        erreur = resultat.stderr
        if isinstance(erreur, bytes):
            erreur = erreur.decode("utf-8", errors="replace")
        raise RuntimeError("sendmail a echoue (code %s) : %s" % (resultat.returncode, (erreur or "").strip()))
