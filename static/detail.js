// Reprend le comportement de l'ecran 2 du programme d'origine :
//  1) alerte visuelle immediate si une valeur n'est pas un nombre, ou si
//     rebut > quantite (controle())
//  2) "Total jour article" recalcule EN DIRECT a chaque frappe, en tenant
//     compte de la saisie en cours de tout le magasin affiche a l'ecran
//     (equivalent de cumul2(), qu'un after_qteN/after_rebutN de l'original
//     appelait a chaque sortie de champ)
//  3) confirmation "Aucun poids de saisi, vous confirmez ?" avant de
//     changer de magasin ou de terminer la journee si tout est a zero
//     (suivant()/precedent()/valider_page2())
//  4) confirmation avant de quitter sans exporter (quit_page2())
//  5) touche ENTREE : passe au champ suivant au lieu de valider le
//     formulaire au hasard du premier bouton non desactive (c'est ce qui
//     provoquait un retour inattendu au 1er magasin) - le serveur
//     continue par ailleurs a tout revalider avant d'enregistrer.
(function () {
  function formatValide(texte) {
    var t = (texte || "").trim();
    if (t === "") return true; // vide = 0, autorise (comme dans l'original)
    return /^-?\d+([.,]\d+)?$/.test(t);
  }

  function totalSaisi(form) {
    var total = 0;
    form.querySelectorAll("input.qte").forEach(function (champ) {
      var v = parseFloat((champ.value || "0").replace(",", "."));
      if (!isNaN(v)) total += v;
    });
    return total;
  }

  function champsInvalides(form) {
    var invalides = [];
    form.querySelectorAll("input.qte, input.rebut").forEach(function (champ) {
      if (!formatValide(champ.value)) invalides.push(champ);
    });
    return invalides;
  }

  function controleLigne(champQte) {
    var cibleId = champQte.getAttribute("data-rebut-cible");
    var champRebut = cibleId ? document.getElementById(cibleId) : null;

    champQte.classList.toggle("alerte", !formatValide(champQte.value));
    if (!champRebut) return;
    champRebut.classList.toggle("alerte", !formatValide(champRebut.value));

    if (formatValide(champQte.value) && formatValide(champRebut.value)) {
      var qte = parseFloat((champQte.value || "0").replace(",", "."));
      var rebut = parseFloat((champRebut.value || "0").replace(",", "."));
      if (!isNaN(qte) && !isNaN(rebut) && rebut > qte) {
        champRebut.classList.add("alerte");
      }
    }
  }

  // "Total jour article" = total deja enregistre pour TOUS LES AUTRES
  // magasins (base envoyee par le serveur, cf. detail.html) + somme, en
  // direct, des quantites moins rebuts de TOUTES les lignes du magasin
  // actuellement affiche a l'ecran qui partagent le meme code article
  // (normalement une seule, mais on gere le cas general).
  function majTotaux(form) {
    var baseEl = document.getElementById("totaux-hors-magasin");
    if (!baseEl) return;
    var base;
    try {
      base = JSON.parse(baseEl.textContent || "{}");
    } catch (e) {
      base = {};
    }

    var saisieParArticle = {};
    form.querySelectorAll("input.qte").forEach(function (champQte) {
      var codart = champQte.getAttribute("data-codart");
      var cibleId = champQte.getAttribute("data-rebut-cible");
      var champRebut = cibleId ? document.getElementById(cibleId) : null;
      var qte = parseFloat((champQte.value || "0").replace(",", ".")) || 0;
      var rebut = champRebut ? (parseFloat((champRebut.value || "0").replace(",", ".")) || 0) : 0;
      saisieParArticle[codart] = (saisieParArticle[codart] || 0) + (qte - rebut);
    });

    form.querySelectorAll("td.total").forEach(function (cellule) {
      var codart = cellule.getAttribute("data-codart");
      var total = (base[codart] || 0) + (saisieParArticle[codart] || 0);
      cellule.textContent = Math.round(total * 1000) / 1000;
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("form-detail");
    if (form) {
      form.querySelectorAll("input.qte").forEach(function (champQte) {
        champQte.addEventListener("input", function () {
          controleLigne(champQte);
          majTotaux(form);
        });
      });
      form.querySelectorAll("input.rebut").forEach(function (champRebut) {
        champRebut.addEventListener("input", function () {
          var champQte = form.querySelector('input.qte[data-rebut-cible="' + champRebut.id + '"]');
          if (champQte) controleLigne(champQte);
          majTotaux(form);
        });
      });

      // Touche ENTREE : passe au champ suivant (comme la tabulation),
      // au lieu de valider le formulaire via le premier bouton non
      // desactive (Precedent, Suivant... selon le magasin affiche) -
      // c'est ce qui provoquait un retour inattendu vers un autre magasin.
      var champs = Array.prototype.slice.call(form.querySelectorAll("input.qte, input.rebut"));
      champs.forEach(function (champ, index) {
        champ.addEventListener("keydown", function (evt) {
          if (evt.key !== "Enter") return;
          evt.preventDefault();
          var suivant = champs[index + 1];
          if (suivant) {
            suivant.focus();
            suivant.select();
          } else {
            var boutonEnregistrer = form.querySelector('button[value="save"]');
            if (boutonEnregistrer) boutonEnregistrer.focus();
          }
        });
      });

      // Filet de securite valable quelle que soit la maniere dont le
      // formulaire est envoye (clic ou ENTREE) : on bloque tant qu'un
      // champ affiche en rouge (valeur non numerique) n'est pas corrige.
      form.addEventListener("submit", function (evt) {
        var invalides = champsInvalides(form);
        if (invalides.length > 0) {
          evt.preventDefault();
          window.alert("Corrigez les valeurs invalides (en rouge) avant de continuer.");
          invalides[0].focus();
          invalides[0].select();
        }
      });

      form.querySelectorAll('button[name="action"]').forEach(function (bouton) {
        bouton.addEventListener("click", function (evt) {
          var action = bouton.value;
          if (["suivant", "precedent", "save_current"].indexOf(action) === -1) return;
          if (champsInvalides(form).length > 0) return; // le handler "submit" ci-dessus bloquera et alertera
          if (totalSaisi(form) === 0) {
            if (!window.confirm("Aucun poids de saisi, vous confirmez ?")) {
              evt.preventDefault();
            }
          }
        });
      });

      // Etat initial (utile si la page est redisplayee apres une erreur
      // avec les valeurs telles que l'utilisateur les avait saisies).
      form.querySelectorAll("input.qte").forEach(controleLigne);
      majTotaux(form);
    }

    var formQuitter = document.getElementById("form-quitter");
    if (formQuitter) {
      formQuitter.addEventListener("submit", function (evt) {
        if (!window.confirm("Confirmer la sortie (SANS export des fichiers) ?")) {
          evt.preventDefault();
        }
      });
    }
  });
})();
