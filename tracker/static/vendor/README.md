# Vendored front-end assets

Served locally (no CDN) so a strict Content-Security-Policy is possible. Do not edit by hand.

| File | Source | Version | Licence |
|------|--------|---------|---------|
| `bootstrap.min.css` | https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css | 5.3.3 | MIT |
| `tom-select.bootstrap5.min.css` | https://cdn.jsdelivr.net/npm/tom-select@2.3.1/dist/css/tom-select.bootstrap5.min.css | 2.3.1 | Apache-2.0 |
| `tom-select.complete.min.js` | https://cdn.jsdelivr.net/npm/tom-select@2.3.1/dist/js/tom-select.complete.min.js | 2.3.1 | Apache-2.0 |

The trailing `sourceMappingURL` comment of each file is removed (the `.map` files are not shipped, and
`ManifestStaticFilesStorage` fails on a missing map at `collectstatic`).

To upgrade: download the new version with `curl`, strip the map comment (CSS: `sed -i -E 's|/\*# sourceMappingURL=[^*]*\*/||' <file>`, JS: `sed -i -E 's|//# sourceMappingURL=.*$||' <file>`), update this table, run `pytest -m e2e`.
