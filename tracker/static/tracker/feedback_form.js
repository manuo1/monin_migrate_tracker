// Creation form: the description label follows the selected type; copied attachments can be removed from the copy.
(function () {
  "use strict";
  var labels = {
    bug: "Description du problème",
    test_passed: "Ce qui a été testé",
    suggestion: "Amélioration proposée",
  };
  var select = document.getElementById("id_type");
  var label = document.querySelector("label[for=id_description]");
  if (select && label) {
    var update = function () { label.textContent = labels[select.value] || "Description"; };
    select.addEventListener("change", update);
    update();
  }

  document.querySelectorAll("[data-remove-parent]").forEach(function (button) {
    button.addEventListener("click", function () { button.parentElement.remove(); });
  });
})();
