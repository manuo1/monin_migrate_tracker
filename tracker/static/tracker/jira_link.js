// Vendor ticket forms (edit + create): while the Jira reference is typed, the "Lien" field follows it.
// The reference widget carries data-jira-base (browse URL), data-ref-prefix and data-link-target (id of the link field).
// A bare prefix (number not typed yet) or an empty reference leaves the link untouched.
(function () {
  const ref = document.querySelector("[data-jira-base]");
  if (!ref) return;
  const link = document.getElementById(ref.dataset.linkTarget);
  if (!link) return;
  const base = ref.dataset.jiraBase;
  const prefix = ref.dataset.refPrefix;

  ref.addEventListener("input", function () {
    const value = ref.value.trim();
    if (value && value !== prefix) link.value = base + value;
  });
})();
