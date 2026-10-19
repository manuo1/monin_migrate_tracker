// Attachment viewer: click opens, left/right arrows navigate, Escape closes.
// Expects .attachment-item links (data-kind, data-url, data-name, data-date, data-remove-url for staff)
// and the #attachment-viewer markup of the feedback page.
(function () {
  "use strict";
  var items = Array.prototype.slice.call(document.querySelectorAll(".attachment-item"));
  var viewer = document.getElementById("attachment-viewer");
  if (!items.length || !viewer) return;

  var content = document.getElementById("viewer-content");
  var caption = document.getElementById("viewer-caption");
  var prev = document.getElementById("viewer-prev");
  var next = document.getElementById("viewer-next");
  var deleteForm = document.getElementById("viewer-delete-form");
  var index = 0;

  function show(i) {
    index = (i + items.length) % items.length;
    var d = items[index].dataset;
    var el;
    if (deleteForm) deleteForm.action = d.removeUrl || "";
    content.innerHTML = "";
    if (d.kind === "image") {
      el = document.createElement("img");
      el.style.cssText = "max-width:100%; max-height:100%; object-fit:contain";
      el.src = d.url;
    } else if (d.kind === "video") {
      el = document.createElement("video");
      el.controls = true;
      el.autoplay = true;
      el.style.cssText = "max-width:100%; max-height:100%";
      el.src = d.url;
    } else if (d.kind === "pdf") {
      el = document.createElement("iframe");
      el.style.cssText = "width:100%; height:100%; background:#fff; border:0";
      el.src = d.url;
    } else {
      el = document.createElement("div");
      el.className = "text-center text-white";
      var title = document.createElement("div");
      title.className = "h4 mb-3 text-break";
      title.textContent = d.name;
      var info = document.createElement("div");
      info.className = "mb-3 text-white-50";
      info.textContent = "Pas d'aperçu pour ce type de fichier.";
      var download = document.createElement("a");
      download.href = d.url;
      download.className = "btn btn-light";
      download.textContent = "Télécharger le fichier";
      el.appendChild(title);
      el.appendChild(info);
      el.appendChild(download);
    }
    content.appendChild(el);
    caption.innerHTML = "";
    var link = document.createElement("a");
    link.href = d.url;
    link.target = "_blank";
    link.rel = "noopener";
    link.className = "text-white";
    link.textContent = d.name;
    caption.appendChild(link);
    caption.appendChild(document.createTextNode(" · " + d.date + " · " + (index + 1) + "/" + items.length));
    prev.style.display = next.style.display = items.length > 1 ? "" : "none";
  }

  function open(i) {
    viewer.style.display = "block";
    document.body.style.overflow = "hidden";
    show(i);
  }

  function close() {
    viewer.style.display = "none";
    document.body.style.overflow = "";
    content.innerHTML = "";
  }

  items.forEach(function (item, i) {
    item.addEventListener("click", function (e) {
      e.preventDefault();
      open(i);
    });
  });
  prev.addEventListener("click", function () { show(index - 1); });
  next.addEventListener("click", function () { show(index + 1); });
  document.getElementById("viewer-close").addEventListener("click", close);
  viewer.addEventListener("click", function (e) {
    if (e.target === viewer || e.target === content) close();
  });
  document.addEventListener("keydown", function (e) {
    if (viewer.style.display === "none") return;
    if (e.key === "Escape") close();
    else if (e.key === "ArrowLeft") show(index - 1);
    else if (e.key === "ArrowRight") show(index + 1);
  });
  if (deleteForm) {
    deleteForm.addEventListener("submit", function (e) {
      if (!window.confirm("Supprimer cette pièce jointe ?")) e.preventDefault();
    });
  }
})();
