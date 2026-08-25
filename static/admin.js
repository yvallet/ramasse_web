// Ecrans d'administration (magasins / fournisseurs / articles / types) :
//  1) confirmation avant toute suppression (equivalent de confirmer_sup())
//  2) sur la fiche magasin, ajout/retrait de lignes d'article a la volee
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("form.form-suppression").forEach(function (form) {
      form.addEventListener("submit", function (evt) {
        var message = form.getAttribute("data-confirm") || "Confirmer la suppression ?";
        if (!window.confirm(message)) {
          evt.preventDefault();
        }
      });
    });

    var tableLignes = document.getElementById("table-lignes");
    var modele = document.getElementById("modele-ligne");
    var boutonAjouter = document.getElementById("bouton-ajouter-ligne");

    if (tableLignes && modele && boutonAjouter) {
      boutonAjouter.addEventListener("click", function () {
        var corps = tableLignes.querySelector("tbody");
        corps.appendChild(modele.content.cloneNode(true));
      });

      tableLignes.addEventListener("click", function (evt) {
        if (evt.target.classList.contains("bouton-retirer-ligne")) {
          var ligne = evt.target.closest("tr");
          if (ligne) ligne.remove();
        }
      });

      // Pre-remplit la designation avec le libelle de l'article choisi
      // dans la liste deroulante, uniquement si le champ est encore vide
      // (ne touche pas a une designation deja personnalisee).
      tableLignes.addEventListener("change", function (evt) {
        if (!evt.target.classList.contains("select-article")) return;
        var ligne = evt.target.closest("tr");
        var libart = ligne && ligne.querySelector('input[name="libart"]');
        var option = evt.target.selectedOptions[0];
        if (libart && !libart.value && option && option.dataset.libelle) {
          libart.value = option.dataset.libelle;
        }
      });
    }
  });
})();
