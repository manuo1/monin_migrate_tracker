// Filter bar of the list pages: selects submit on change, the search box submits after a short pause
// (3 characters minimum, or empty to clear) and gets its focus back after the reload.
(function () {
  const form = document.querySelector("form[data-list-filters]");
  if (!form) return;

  form.querySelectorAll("select[data-autosubmit]").forEach(function (select) {
    select.addEventListener("change", function () {
      const resetName = select.dataset.resetField;
      if (resetName && form.elements[resetName]) form.elements[resetName].value = "";
      form.submit();
    });
  });

  const q = form.elements["q"];
  if (!q) return;
  let timer;
  q.addEventListener("input", function () {
    clearTimeout(timer);
    const length = q.value.trim().length;
    if (length === 0 || length >= 3) {
      timer = setTimeout(function () {
        sessionStorage.setItem("refocusQ", "1");
        form.submit();
      }, 350);
    }
  });
  if (sessionStorage.getItem("refocusQ")) {
    sessionStorage.removeItem("refocusQ");
    q.focus();
    q.setSelectionRange(q.value.length, q.value.length);
  }
})();
