/**
 * core/static/core/confirm-submit.js
 * ====================================
 * CSP-safe confirm dialogs for forms with data-confirm attribute.
 * Replaces inline onsubmit="return confirm(...)" handlers.
 *
 * Usage: Add data-confirm="Are you sure?" to any form element.
 */
(function () {
  'use strict';

  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (form.tagName !== 'FORM') return;
    var msg = form.getAttribute('data-confirm');
    if (msg && !confirm(msg)) {
      e.preventDefault();
      var submit = form.querySelector('button[type="submit"]:disabled');
      if (submit) {
        submit.disabled = false;
        var originalText = submit.getAttribute('data-original-text');
        if (originalText) submit.textContent = originalText;
      }
    }
  });
})();
