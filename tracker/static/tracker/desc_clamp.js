// Long descriptions are clamped in the list: a click unfolds / folds them.
(function () {
  document.querySelectorAll(".desc-clamp").forEach(function (el) {
    el.addEventListener("click", function () {
      if (window.getSelection().toString()) return; // do not collapse while selecting text
      el.classList.toggle("open");
    });
  });
})();
