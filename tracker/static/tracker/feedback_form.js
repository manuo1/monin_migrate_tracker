// Creation form: the description label follows the selected type; copied attachments can be removed from the copy.
(function () {
  "use strict";
  var texts = document.getElementById("js-strings").dataset; // translated by the template
  var labels = {
    bug: texts.labelBug,
    test_passed: texts.labelTestPassed,
    suggestion: texts.labelSuggestion,
  };
  var select = document.getElementById("id_type");
  var label = document.querySelector("label[for=id_description]");
  if (select && label) {
    var update = function () { label.textContent = labels[select.value] || texts.labelDefault; };
    select.addEventListener("change", update);
    update();
  }

  document.querySelectorAll("[data-remove-parent]").forEach(function (button) {
    button.addEventListener("click", function () { button.parentElement.remove(); });
  });
})();
