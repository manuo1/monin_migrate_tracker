// Page and tab inputs: reference list with search (Tom Select); free entry stays possible.
// Inputs carry list="reference-pages" or list="reference-tabs"; the datalists in #reference-lists give the values.
// For staff (data-staff="true"), a value outside the list is highlighted.
(function () {
  "use strict";
  if (!window.TomSelect) return; // CDN unreachable: the plain input + datalist still work.
  var container = document.getElementById("reference-lists");
  var texts = document.getElementById("js-strings").dataset; // translated by the template
  var staff = container !== null && container.dataset.staff === "true";

  document.querySelectorAll("input[list='reference-pages'], input[list='reference-tabs']").forEach(function (input) {
    var values = Array.prototype.map.call(
      document.querySelectorAll("#" + input.getAttribute("list") + " option"),
      function (option) { return option.value; }
    );
    var current = input.value.trim();
    // The stored value stays displayed even when it is not in the reference list.
    var options = current && values.indexOf(current) === -1 ? [current].concat(values) : values;
    var select = new TomSelect(input, {
      options: options.map(function (v) { return { value: v, text: v }; }),
      items: current ? [current] : [],
      delimiter: "\u001f", // page names may contain commas
      maxItems: 1,
      maxOptions: null,
      create: true,
      createOnBlur: true,
      persist: false,
      selectOnTab: true,
      placeholder: texts.refPlaceholder,
      render: {
        option_create: function (data, escape) {
          var parts = texts.refCreate.split("{value}");
          return '<div class="create">' + escape(parts[0]) + "<strong>" + escape(data.input) + "</strong>" + escape(parts[1] || "") + "</div>";
        },
        no_results: function (data, escape) {
          return '<div class="no-results">' + escape(texts.refNoMatch) + "</div>";
        },
      },
    });

    function mark() {
      if (!staff) return;
      var value = (select.getValue() || "").trim();
      var outside = value !== "" && values.indexOf(value) === -1;
      select.control.classList.toggle("bg-warning-subtle", outside);
      select.control.classList.toggle("border-warning", outside);
      select.control.title = outside ? texts.refOutside : "";
    }
    select.on("change", mark);
    mark();
  });
})();
