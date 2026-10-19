// Drag and drop + paste (Ctrl+V) of files and screenshots.
// Expects #attachment-zone (contains the file input) and #attachment-staged.
// data-auto on the zone: files are sent immediately (feedback page).
// Otherwise: thumbnails with a remove button are shown until the form is saved (creation page).
(function () {
  "use strict";
  var zone = document.getElementById("attachment-zone");
  var input = zone && zone.querySelector("input[type=file]");
  var staged = document.getElementById("attachment-staged");
  if (!input || !staged) return;

  var auto = !!zone.dataset.auto;
  var transfer = new DataTransfer();
  var objectUrls = [];

  function fileNames() {
    return Array.from(transfer.files).map(function (f) { return f.name; }).join(", ");
  }

  function removeAt(index) {
    var next = new DataTransfer();
    Array.from(transfer.files).forEach(function (f, j) { if (j !== index) next.items.add(f); });
    transfer = next;
    refresh(false);
  }

  function thumbnail(file, index) {
    var box = document.createElement("div");
    box.className = "position-relative border rounded p-1 bg-white text-center";
    box.style.width = "110px";
    var preview;
    var isImage = file.type.indexOf("image/") === 0;
    var isVideo = file.type.indexOf("video/") === 0;
    if (isImage || isVideo) {
      var url = URL.createObjectURL(file);
      objectUrls.push(url);
      preview = document.createElement(isImage ? "img" : "video");
      preview.src = isVideo ? url + "#t=0.1" : url;
      if (isVideo) { preview.muted = true; preview.preload = "metadata"; }
      preview.style.cssText = "height:70px; max-width:100%; object-fit:cover";
    } else {
      preview = document.createElement("div");
      preview.className = "bg-light d-flex align-items-center justify-content-center fw-bold text-secondary";
      preview.style.height = "70px";
      preview.textContent = file.type === "application/pdf" ? "PDF" : "FICHIER";
    }
    var name = document.createElement("div");
    name.className = "small text-truncate";
    name.title = file.name;
    name.textContent = file.name;
    var remove = document.createElement("button");
    remove.type = "button";
    remove.className = "btn btn-sm btn-danger position-absolute top-0 end-0 py-0 px-1";
    remove.title = "Retirer";
    remove.textContent = "✕";
    remove.addEventListener("click", function () { removeAt(index); });
    box.appendChild(preview);
    box.appendChild(name);
    box.appendChild(remove);
    return box;
  }

  function refresh(send) {
    input.files = transfer.files;
    objectUrls.forEach(function (u) { URL.revokeObjectURL(u); });
    objectUrls = [];
    staged.innerHTML = "";
    if (auto) {
      if (send && transfer.files.length) {
        staged.textContent = "Envoi en cours : " + fileNames();
        input.form.submit();
      }
      return;
    }
    staged.className = transfer.files.length ? "d-flex flex-wrap gap-2 mt-2" : "small mt-1";
    Array.from(transfer.files).forEach(function (f, i) { staged.appendChild(thumbnail(f, i)); });
  }

  function addFiles(files) {
    Array.from(files).forEach(function (f, i) {
      // Pasted screenshots are all named "image.png": give them a unique name.
      if (/^image\.(png|jpe?g|gif|webp)$/i.test(f.name)) {
        f = new File([f], "capture_" + Date.now() + "_" + i + "." + f.name.split(".").pop(), { type: f.type });
      }
      transfer.items.add(f);
    });
    refresh(true);
  }

  function dragHasFiles(e) {
    return e.dataTransfer && Array.from(e.dataTransfer.types || []).indexOf("Files") !== -1;
  }

  // "Browse": adds to what is already staged (creation) or sends right away (feedback page).
  input.addEventListener("change", function () {
    var chosen = Array.from(input.files);
    if (auto) transfer = new DataTransfer();
    chosen.forEach(function (f) { transfer.items.add(f); });
    refresh(true);
  });

  ["dragenter", "dragover"].forEach(function (name) {
    zone.addEventListener(name, function (e) {
      if (!dragHasFiles(e)) return;
      e.preventDefault();
      zone.classList.add("bg-primary-subtle");
    });
  });
  zone.addEventListener("dragleave", function (e) {
    if (!zone.contains(e.relatedTarget)) zone.classList.remove("bg-primary-subtle");
  });
  zone.addEventListener("drop", function (e) {
    zone.classList.remove("bg-primary-subtle");
    if (!dragHasFiles(e)) return;
    e.preventDefault();
    addFiles(e.dataTransfer.files);
  });

  // Ctrl+V anywhere on the page: screenshot or copied file.
  document.addEventListener("paste", function (e) {
    var files = e.clipboardData && e.clipboardData.files;
    if (files && files.length) {
      e.preventDefault();
      addFiles(files);
    }
  });
})();
