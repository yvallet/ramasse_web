// Reprend le comportement de before_date/after_date de ramasse10_sql.py :
// afficher le nom du jour correspondant a la date saisie, sans aller-retour serveur.
(function () {
  var NOMS = ["Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"];

  function parseJJMMAAAA(txt) {
    var m = /^(\d{2})[\/.\-](\d{2})[\/.\-](\d{4})$/.exec((txt || "").trim());
    if (!m) return null;
    var jj = parseInt(m[1], 10), mm = parseInt(m[2], 10), aa = parseInt(m[3], 10);
    var d = new Date(aa, mm - 1, jj);
    if (d.getFullYear() !== aa || d.getMonth() !== mm - 1 || d.getDate() !== jj) return null;
    return d;
  }

  function maj() {
    var champ = document.getElementById("date");
    var sortie = document.getElementById("jour");
    if (!champ || !sortie) return;
    var d = parseJJMMAAAA(champ.value);
    sortie.textContent = d ? NOMS[d.getDay()] : "";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var champ = document.getElementById("date");
    if (champ) {
      champ.addEventListener("input", maj);
      champ.addEventListener("blur", maj);
    }
  });
})();
