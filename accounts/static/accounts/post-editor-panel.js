/**
 * accounts/static/accounts/post-editor-panel.js
 * ================================================
 * Panel-specific JavaScript for the new-post and edit-post admin pages.
 * Loaded via {% static 'accounts/post-editor-panel.js' %} in
 * _post_editor_scripts.html — CSP-safe (no unsafe-inline required).
 *
 * Features
 * --------
 * 1. Post form UX        – disable submit button while saving; re-enable on error.
 * 2. Slug auto-generation – derives a URL slug from the title as the user types,
 *                           stopping once the slug field is manually edited.
 * 3. Dynamic subcategory – populates the subcategory <select> via AJAX when the
 *                          category changes, using the correct language's name.
 */

(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {

    // ── 1. Post form – disable submit button while saving ────────────────
    // Disables the "Save" button once the form is submitted to prevent double-
    // saves (e.g. from impatient double-clicks on a slow connection).
    // Re-enables the button if the server returns with validation errors.
    var postForm = document.querySelector('.panel-form--post');
    var postSubmitBtn = document.getElementById('edit-post-submit');
    if (postForm && postSubmitBtn) {
      // If the server returned the page with errors, the button stays enabled.
      if (document.querySelector('.panel-form--post .errorlist')) {
        postSubmitBtn.disabled = false;
      }
      postForm.addEventListener('submit', function () {
        if (!postForm.checkValidity()) return;   // Don't lock if HTML5 validation fires.
        postSubmitBtn.disabled = true;
        postSubmitBtn.textContent = postSubmitBtn.dataset.loadingText || 'Saving\u2026';
      });
    }

    // ── 2. Slug auto-generation from title ──────────────────────────────
    // As the user types in the title field, a URL-safe slug is derived and
    // mirrored into the slug field automatically.
    // Once the user manually edits the slug field, auto-generation stops so
    // that the manual value is not overwritten.
    var titleInput = document.getElementById('id_title');
    var slugInput  = document.getElementById('id_slug');
    if (titleInput && slugInput) {
      // If the slug field already has a value (edit mode), don't overwrite it.
      var slugEdited = slugInput.value.length > 0;

      // Mark the slug as user-edited as soon as the field is modified.
      slugInput.addEventListener('input', function () { slugEdited = true; });

      titleInput.addEventListener('input', function () {
        if (!slugEdited) {
          // Regex removes anything that isn't:
          //   a-z, 0-9, Unicode Persian characters (\u0600-\u06FF), space, or hyphen.
          // Whitespace runs are collapsed to single hyphens.
          slugInput.value = this.value
            .toLowerCase()
            .replace(/[^a-z0-9\u0600-\u06FF\s-]/g, '')
            .trim()
            .replace(/\s+/g, '-');
        }
      });
    }

    // ── 3. Dynamic subcategory select (AJAX) ────────────────────────────
    // When the category dropdown changes, fetches the subcategories that
    // belong to the newly selected category from the server and repopulates
    // the subcategory dropdown.
    //
    // Language handling: reads the <html lang="..."> attribute to build the
    // correct URL prefix (e.g. /en/ or /fa/) so the AJAX call is routed to
    // the correct i18n_patterns URL.  Also picks the localised subcategory
    // name (name_fa vs name_en) based on the active language.
    var catSelect = document.getElementById('id_category');
    var subSelect = document.getElementById('id_subcategory');
    if (catSelect && subSelect) {
      // Read language from <html lang> — avoids hard-coding 'en' / 'fa'.
      var lang = document.documentElement.lang || 'en';
      var prefix = '/' + lang;
      var isFa = lang === 'fa';

      catSelect.addEventListener('change', function () {
        var catId = this.value;
        // Show loading state while fetching subcategories.
        subSelect.disabled = true;
        var loadingText = subSelect.dataset.loadingText || 'Loading\u2026';
        subSelect.innerHTML = '<option value="">' + loadingText + '</option>';
        if (!catId) {
          subSelect.disabled = false;
          subSelect.innerHTML = '<option value="">---------</option>';
          return;
        }

        // Fetch subcategories for the selected category ID.
        fetch(prefix + '/posts/subcategories/?category=' + catId)
          .then(function (r) { return r.json(); })
          .then(function (data) {
            subSelect.innerHTML = '<option value="">---------</option>';
            data.forEach(function (sub) {
              var opt = document.createElement('option');
              opt.value = sub.id;
              opt.textContent = (isFa && sub.name_fa) ? sub.name_fa : sub.name_en;
              subSelect.appendChild(opt);
            });
          })
          .catch(function () {
            var errorText = subSelect.dataset.errorText || 'Error loading subcategories';
            subSelect.innerHTML = '<option value="">' + errorText + '</option>';
          })
          .finally(function () {
            subSelect.disabled = false;
          });
      });
    }

  });
})();
