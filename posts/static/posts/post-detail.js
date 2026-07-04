/**
 * posts/static/posts/post-detail.js
 * ===================================
 * Minimal JavaScript for the post detail page.
 * CSP-safe — no inline scripts needed.
 *
 * Feature
 * -------
 * Copy-link button: when clicked, writes the current page URL to the
 * system clipboard and briefly changes the button label to a "Copied!"
 * confirmation before reverting to the default label.
 *
 * Text labels are read from data-* attributes set by the Django template
 * (via {% trans %}) rather than being hard-coded here, so they work in
 * both English and Persian without changes to this file.
 */

(function () {
  'use strict';

  var btn = document.getElementById('copy-link-btn');
  if (!btn) return;   // Button not present on this page variant — bail out.

  btn.addEventListener('click', function () {
    var label      = btn.querySelector('.share-btn-label');
    var copiedMsg  = btn.dataset.copiedText  || 'Copied!';
    var defaultMsg = btn.dataset.defaultText || 'Copy link';

    // navigator.clipboard requires a secure context (HTTPS or localhost).
    navigator.clipboard.writeText(window.location.href).then(function () {
      if (label) label.textContent = copiedMsg;
      setTimeout(function () { if (label) label.textContent = defaultMsg; }, 2000);
    }).catch(function () {
      var fallback = document.createElement('textarea');
      fallback.value = window.location.href;
      fallback.style.cssText = 'position:fixed;left:-9999px';
      document.body.appendChild(fallback);
      fallback.select();
      try { document.execCommand('copy'); } catch (_) {}
      document.body.removeChild(fallback);
      if (label) label.textContent = copiedMsg;
      setTimeout(function () { if (label) label.textContent = defaultMsg; }, 2000);
    });
  });
})();
