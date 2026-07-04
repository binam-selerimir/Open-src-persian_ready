/**
 * accounts/static/accounts/taxonomy.js
 * ======================================
 * JavaScript for the admin taxonomy management page (/panel/taxonomy/).
 * Replaces the inline <script> block — CSP-safe.
 *
 * Features
 * --------
 * 1. Tab highlighting  – reads the URL hash (#categories, #subcategories,
 *                        #post-types) and marks the matching tab as active.
 *                        Updates when the hash changes (tab click or browser nav).
 * 2. Color picker sync – updates a live hex-value hint label next to each
 *                        PostType color input as the user picks a colour.
 */

(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {

    // ── 1. Tab highlight based on URL hash ──────────────────────────────
    // The taxonomy page has three anchor-linked tabs (#categories,
    // #subcategories, #post-types). The active tab and its section are
    // highlighted based on the current URL hash.
    var tabs     = document.querySelectorAll('[data-taxonomy-tab]');
    var sections = document.querySelectorAll('.taxonomy-section');

    /** Apply active classes to the tab and section matching the current hash. */
    function setActiveTab() {
      var hash = window.location.hash || '#categories';   // Default to first tab.
      tabs.forEach(function (tab) {
        tab.classList.toggle('taxonomy-tab--active', tab.getAttribute('href') === hash);
      });
      sections.forEach(function (section) {
        section.classList.toggle('taxonomy-section--highlight', '#' + section.id === hash);
      });
    }

    // Defer setActiveTab() on tab click so the hash has updated by the time
    // the function runs (hash update fires before the event handler otherwise).
    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () { setTimeout(setActiveTab, 0); });
    });
    window.addEventListener('hashchange', setActiveTab);
    setActiveTab();   // Set correct tab on initial page load.

    // ── 2. Color picker live hex-value preview ──────────────────────────
    // Shows the currently selected hex value next to each PostType color
    // input so the editor doesn't have to guess from the swatch alone.
    document.querySelectorAll('.panel-input--color').forEach(function (input) {
      var field = input.closest('.taxonomy-color-field');
      var hint  = field ? field.querySelector('.taxonomy-color-hint') : null;
      if (!hint) return;
      /** Sync the hint label text to the current input value. */
      function sync() { hint.textContent = input.value; }
      input.addEventListener('input', sync);
      sync();   // Initialise with the current value on page load.
    });

  });
})();
