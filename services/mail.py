# coding: utf8
"""
Envoi d'e-mail simple par SMTP (stdlib uniquement, aucune dependance
supplementaire) - utilise pour le lien de reinitialisation de mot de passe
(voir auth.py). Fonctionnalite absente de l'original (application desktop
mono-poste).

Si SMTP_HOST n'est pas configure (voir config.py), envoyer() n'echoue pas :
elle journalise le message en entier via le logger fourni. C'est le mode
attendu en local/developpement, ou aucun serveur SMTP n'est disponible - le
lien de reinitialisation se lit alors dans logs/app.log.
"""
import smtplib
from email.message import EmailMessage


def envoyer(config, destinataire, sujet, corps_texte, logger=None):
    """
    Envoie un e-mail texte simple. `config` : mapping donnant acces a
    SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD/SMTP_FROM/SMTP_STARTTLS
    (app.config convient tel quel).

    Sans SMTP_HOST configure : ne leve jamais, journalise le contenu complet
    (sujet + corps, donc le lien) via `logger` si fourni, sinon ne fait
    rien - c'est a l'appelant de fournir un logger en production pour ne pas
    perdre silencieusement un envoi.

    Leve RuntimeError si SMTP_HOST est configure mais que l'envoi echoue
    (connexion refusee, authentification refusee...) : l'appelant decide
    quoi en faire (ex. message d'erreur generique a l'utilisateur).
    """
    hote = config.get("SMTP_HOST")
    if not hote:
        if logger is not None:
            logger.warning(
                "SMTP non configure - e-mail non envoye a %s. Sujet : %s\n%s",
                destinataire, sujet, corps_texte,
            )
        return False

    message = EmailMessage()
    message["Subject"] = sujet
    message["From"] = config.get("SMTP_FROM") or config.get("SMTP_USER") or "no-reply@localhost"
    message["To"] = destinataire
    message.set_content(corps_texte)

    port = int(config.get("SMTP_PORT") or 587)
    try:
        with smtplib.SMTP(hote, port, timeout=10) as serveur:
            if config.get("SMTP_STARTTLS", True):
                serveur.starttls()
            if config.get("SMTP_USER"):
                serveur.login(config["SMTP_USER"], config.get("SMTP_PASSWORD") or "")
            serveur.send_message(message)
    except (OSError, smtplib.SMTPException) as e:
        raise RuntimeError("Envoi de l'e-mail a %s echoue : %s" % (destinataire, e))

    return True
