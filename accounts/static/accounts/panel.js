/**
 * accounts/static/accounts/panel.js
 * ===================================
 * Consolidated JavaScript for all admin panel and auth pages.
 * Replaces all inline <script> blocks so the Content-Security-Policy
 * header can remain free of 'unsafe-inline' for scripts.
 *
 * Loaded via {% static 'accounts/panel.js' %} on every panel page.
 *
 * Sections
 * --------
 * 1. Password visibility toggle  – show/hide password on login & register.
 * 2. Login form UX               – button disable on submit + re-enable on error.
 * 3. Register form UX            – same pattern as login.
 * 4. Bulk-action bar             – shows/hides the "N selected" action bar
 *                                  in the admin post list; handles delete confirm.
 * 5. Taxonomy inline edit toggle – shows/hides inline edit forms on the
 *                                  taxonomy management page.
 */

(function () {
  'use strict';

  // ─── 1. Password visibility toggle (login + register forms) ─────────────
  // Finds all [.password-toggle] buttons and binds them to flip the type of
  // their target input between 'password' and 'text', with accessible ARIA labels.
  document.querySelectorAll('.password-toggle').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var input = document.getElementById(btn.dataset.target);
      if (!input) return;
      var isHidden = input.type === 'password';
      input.type = isHidden ? 'text' : 'password';
      var showLabel = btn.dataset.labelShow || 'Show password';
      var hideLabel = btn.dataset.labelHide || 'Hide password';
      btn.setAttribute('aria-label', isHidden ? hideLabel : showLabel);
      // Swap the eye icon SVG between show/hide states.
      var eyeOpen = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
      var eyeClosed = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>';
      btn.innerHTML = isHidden ? eyeClosed : eyeOpen;
    });
  });

  // ─── 2. Login form ──────────────────────────────────────────────────────
  // Disables the submit button once the form is submitted to prevent double-
  // submits. Re-enables it if the server returns the page with errors, so the
  // user can try again without refreshing.
  var loginForm = document.getElementById('login-form');
  if (loginForm) {
    // Server re-rendered with errors → keep button enabled.
    if (document.querySelector('#login-form .errorlist')) {
      var loginBtn = document.getElementById('login-submit');
      if (loginBtn) loginBtn.disabled = false;
    }

    loginForm.addEventListener('submit', function () {
      if (!loginForm.checkValidity()) return;   // Don't disable if native validation fails.
      var btn = document.getElementById('login-submit');
      if (btn) {
        btn.disabled = true;
        // Show a localised loading label from the button's data attribute.
        btn.textContent = btn.dataset.loadingText || 'Signing in\u2026';
      }
    });
  }

  // ─── 3. Register form ───────────────────────────────────────────────────
  // Same UX pattern as the login form.
  var registerForm = document.getElementById('register-form');
  if (registerForm) {
    if (document.querySelector('#register-form .errorlist')) {
      var registerBtn = document.getElementById('register-submit');
      if (registerBtn) registerBtn.disabled = false;
    }

    registerForm.addEventListener('submit', function () {
      if (!registerForm.checkValidity()) return;
      var btn = document.getElementById('register-submit');
      if (btn) {
        btn.disabled = true;
        btn.textContent = btn.dataset.loadingText || 'Creating account\u2026';
      }
    });
  }

  // ─── 4. Admin post list – bulk-action bar ───────────────────────────────
  // Tracks which post checkboxes are ticked and shows a floating action bar
  // ("N selected – [action dropdown] – Apply") when at least one is checked.
  // Confirms before deleting to prevent accidental mass deletion.

  var bulkBar   = document.getElementById('bulk-bar');
  var bulkCount = document.getElementById('bulk-count');
  var bulkForm  = document.getElementById('bulk-form');

  /** Recalculate the number of checked post checkboxes and update the bar. */
  function updateBulkBar() {
    if (!bulkBar || !bulkCount) return;
    var checked = document.querySelectorAll('.post-checkbox:checked').length;
    bulkBar.style.display = checked > 0 ? 'flex' : 'none';
    var label = bulkCount.dataset.label || 'selected';
    bulkCount.textContent = checked + ' ' + label;
  }

  // Recalculate the count whenever any individual checkbox changes.
  document.querySelectorAll('.post-checkbox').forEach(function (cb) {
    cb.addEventListener('change', updateBulkBar);
  });

  // "Select all" header checkbox toggles all visible post checkboxes.
  var selectAllCb = document.getElementById('select-all');
  if (selectAllCb) {
    selectAllCb.addEventListener('change', function () {
      document.querySelectorAll('.post-checkbox').forEach(function (cb) {
        cb.checked = selectAllCb.checked;
      });
      updateBulkBar();
    });
  }

  // Validate and optionally confirm before the bulk form submits.
  if (bulkForm) {
    bulkForm.addEventListener('submit', function (e) {
      var action = bulkForm.querySelector('[name="bulk_action"]');
      if (!action || !action.value) {
        e.preventDefault();
        alert(bulkForm.dataset.noActionMsg || 'Please select a bulk action.');
        return;
      }
      // Show a confirmation dialog for destructive delete actions.
      if (action.value === 'delete') {
        var msg = bulkForm.dataset.deleteConfirmMsg ||
          'Delete selected posts? This cannot be undone.';
        if (!confirm(msg)) e.preventDefault();
      }
    });
  }

  // ─── 5. Taxonomy inline edit toggle ─────────────────────────────────────
  // Each [data-edit-toggle] button shows or hides the edit form panel whose
  // id matches the button's data-edit-toggle attribute.
  document.querySelectorAll('[data-edit-toggle]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var target = document.getElementById(btn.dataset.editToggle);
      if (!target) return;
      var hidden = target.style.display === 'none' || target.style.display === '';
      target.style.display = hidden ? 'block' : 'none';
    });
  });

  // ─── 6. Certificate edit form toggle ───────────────────────────────────
  // .cert-edit-btn populates the edit form with certificate data.
  // .cert-cancel-btn hides the edit form and shows the create form.
  document.querySelectorAll('.cert-edit-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.getElementById('edit-id').value = btn.dataset.pk;
      document.getElementById('edit-name').value = btn.dataset.name;
      document.getElementById('edit-name-fa').value = btn.dataset.nameFa;
      document.getElementById('edit-desc').value = btn.dataset.desc;
      document.getElementById('edit-desc-fa').value = btn.dataset.descFa;
      document.getElementById('edit-color').value = btn.dataset.color;
      document.getElementById('edit-active').checked = btn.dataset.active === 'true';
      document.getElementById('edit-section').style.display = 'block';
      document.getElementById('create-section').style.display = 'none';
    });
  });

  document.querySelectorAll('.cert-cancel-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.getElementById('edit-section').style.display = 'none';
      document.getElementById('create-section').style.display = 'block';
    });
  });

})();
