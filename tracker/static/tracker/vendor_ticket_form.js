// Vendor ticket creation form: "Copy" buttons (to paste into Jira) and cursor placed at the end of the Jira reference,
// right after the prefix, so only the number is left to type.
(function () {
  document.querySelectorAll("[data-copy-target]").forEach(function (button) {
    button.addEventListener("click", function () {
      const field = document.getElementById(button.dataset.copyTarget);
      if (!field) return;
      const label = button.textContent;
      function done() {
        button.textContent = "Copié";
        setTimeout(function () {
          button.textContent = label;
        }, 1500);
      }
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(field.value).then(done);
      } else {
        // Fallback on a non-secure page (plain http): select the text and use the browser copy command.
        field.select();
        if (document.execCommand("copy")) done();
        field.setSelectionRange(field.value.length, field.value.length);
      }
    });
  });

  const ref = document.querySelector("[data-focus-end]");
  if (ref) {
    ref.focus();
    ref.setSelectionRange(ref.value.length, ref.value.length);
  }
})();
