/**
 * MathJax 3 configuration + auto-init for post pages.
 *
 * Reads \(...\) and \[...\] delimiters from <span class="arithmatex">
 * and <div class="arithmatex"> elements produced by pymdownx.arithmatex
 * (generic mode).
 *
 * Self-hosted MathJax — no CDN dependency, CSP-safe (script-src: 'self').
 */
(function () {
  'use strict';

  window.MathJax = {
    tex: {
      inlineMath: [['\\(', '\\)']],
      displayMath: [['\\[', '\\]']],
      processEscapes: true,
      processEnvironments: true,
    },
    options: {
      ignoreHtmlClass: '.*',
      processHtmlClass: 'arithmatex',
    },
    startup: {
      ready: function () {
        MathJax.startup.defaultReady();
        MathJax.startup.promise.then(function () {
          document.body.classList.add('mathjax-loaded');
        });
      },
    },
  };
})();
