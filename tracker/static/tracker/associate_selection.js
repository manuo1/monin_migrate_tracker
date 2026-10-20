// Association page: the checked vendor tickets are kept in sessionStorage while the staff filters or searches,
// then sent with the form (those not visible on the current page go in hidden fields).
(function () {
  const form = document.getElementById("assoc-form");
  if (!form) return;
  const key = form.dataset.storageKey;
  const counter = document.getElementById("assoc-counter");
  const boxes = Array.prototype.slice.call(document.querySelectorAll(".assoc-cb"));

  let selected;
  try {
    selected = new Set(JSON.parse(sessionStorage.getItem(key) || "[]"));
  } catch (e) {
    selected = new Set();
  }

  function update() {
    counter.textContent = selected.size;
    sessionStorage.setItem(key, JSON.stringify(Array.from(selected)));
  }

  boxes.forEach(function (box) {
    if (selected.has(box.value)) box.checked = true;
    box.addEventListener("change", function () {
      if (box.checked) selected.add(box.value);
      else selected.delete(box.value);
      update();
    });
  });
  update();

  form.addEventListener("submit", function () {
    const visible = new Set(boxes.map(function (box) { return box.value; }));
    selected.forEach(function (id) {
      if (visible.has(id)) return;
      const hidden = document.createElement("input");
      hidden.type = "hidden";
      hidden.name = "tickets";
      hidden.value = id;
      form.appendChild(hidden);
    });
    sessionStorage.removeItem(key);
  });
})();
