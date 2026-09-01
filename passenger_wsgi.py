# coding: utf8
"""
Point d'entree WSGI pour Phusion Passenger (hebergement mutualise o2switch,
cPanel "Setup Python App"). Passenger importe ce fichier et cherche une
variable nommee `application` - voir DEPLOIEMENT_O2SWITCH.md.

Ne sert qu'en production : en local, on continue de lancer `python app.py`
(voir le bloc `if __name__ == "__main__"` de app.py, jamais execute ici).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app as application  # noqa: E402,F401
