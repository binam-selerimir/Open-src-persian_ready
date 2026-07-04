/**
 * core/static/core/main.js
 * ========================
 * Site-wide vanilla JavaScript for the public-facing UI.
 * Loaded in every page via the <script> tag at the bottom of base.html.
 *
 * All sections are wrapped in IIFEs (Immediately Invoked Function Expressions)
 * to keep variables out of the global scope and prevent naming conflicts with
 * other scripts loaded on the page.
 *
 * Sections
 * --------
 * 1. Hamburger menu        – mobile navigation toggle with accessibility support.
 * 2. Active nav link       – highlights the current page link in the navbar.
 * 3. Smooth scroll         – animated scrolling for all #anchor links on the page.
 * 4. Back to top button    – shows/hides a floating "return to top" button.
 * 5. Auto-dismiss messages – fades out Django flash messages after 6 seconds.
 * 6. Submit button lock    – disables the submit button on form submission to
 *                            prevent double-submits, with validity guard.
 * 7. Submit button lock    – disables submit buttons on form submission.
 * 8. Site alert dismiss    – dismisses site alert banner with cookie.
 * 9. Auto-submit selects   – auto-submits forms when data-auto-submit selects change.
 */

'use strict';

/* ── 1. Hamburger menu ──────────────────────────────────────────────────── */
(function () {
  var btn = document.getElementById('hamburger');
  var nav = document.getElementById('main-nav');
  if (!btn || !nav) return;

  function close() {
    nav.classList.remove('open');
    btn.setAttribute('aria-expanded', 'false');
    btn.focus();
  }

  btn.addEventListener('click', function () {
    var expanded = btn.getAttribute('aria-expanded') === 'true';
    btn.setAttribute('aria-expanded', String(!expanded));
    nav.classList.toggle('open');
    if (!expanded) {
      var firstLink = nav.querySelector('a');
      if (firstLink) firstLink.focus();
    }
  });

  nav.querySelectorAll('a').forEach(function (link) {
    link.addEventListener('click', close);
  });

  document.addEventListener('click', function (e) {
    if (nav.classList.contains('open') && !nav.contains(e.target) && !btn.contains(e.target)) close();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && nav.classList.contains('open')) {
      close();
    }
  });
})();

/* ── 2. Highlight active nav link ──────────────────────────────────────── */
(function () {
  // Compare the full pathname to detect the active page and mark its link.
  var path = window.location.pathname;
  document.querySelectorAll('.main-nav a').forEach(function (link) {
    if (link.getAttribute('href') === path) link.classList.add('active');
  });
})();

/* ── 3. Smooth scroll for anchor links ──────────────────────────────────── */
// Intercept clicks on any #anchor link and replace the default browser jump
// with a smooth animated scroll. Respects prefers-reduced-motion.
document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
  anchor.addEventListener('click', function (e) {
    var href = this.getAttribute('href');
    if (href === '#' || href.length < 2) return;
    var target = document.querySelector(href);
    if (target) {
      e.preventDefault();
      var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      target.scrollIntoView({ behavior: prefersReduced ? 'auto' : 'smooth', block: 'start' });
    }
  });
});

/* ── 4. Back to top button ───────────────────────────────────────────────── */
(function () {
  var btn = document.getElementById('back-to-top');
  if (!btn) return;

  // Show the button once the user has scrolled 400 px down; hide it again above.
  // { passive: true } tells the browser this listener won't call preventDefault(),
  // allowing the browser to optimise scroll performance.
  window.addEventListener('scroll', function () {
    btn.classList.toggle('visible', window.scrollY > 400);
  }, { passive: true });

  btn.addEventListener('click', function () {
    var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({ top: 0, behavior: prefersReduced ? 'auto' : 'smooth' });
  });
})();

/* ── 5. Auto-dismiss flash messages ────────────────────────────────────── */
(function () {
  // Delegated close handler — replaces inline onclick (CSP-safe).
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.message-close');
    if (btn) btn.parentElement.remove();
  });

  // Find all Django flash messages (.message) and schedule their removal.
  var msgs = document.querySelectorAll('.message');
  var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  msgs.forEach(function (msg) {
    setTimeout(function () {
      if (prefersReduced) {
        msg.remove();
      } else {
        msg.style.transition = 'opacity 0.5s';
        msg.style.opacity = '0';
        setTimeout(function () { msg.remove(); }, 500);
      }
    }, 6000);
  });
})();

/* ── 5b. Character counter for textareas with maxlength ────────────────── */
(function () {
  document.querySelectorAll('textarea[maxlength]').forEach(function (ta) {
    var max = parseInt(ta.getAttribute('maxlength'), 10);
    if (!max) return;
    var counter = ta.parentElement.querySelector('.form-char-count');
    if (!counter) {
      counter = document.createElement('div');
      counter.className = 'form-char-count';
      ta.parentElement.appendChild(counter);
    }
    function update() {
      var len = ta.value.length;
      counter.textContent = len + ' / ' + max;
      counter.classList.toggle('form-char-count--warn', len >= max * 0.9);
    }
    ta.addEventListener('input', update);
    update();
  });
})();

/* ── 6. Auto-submit dropdown loading state ───────────────────────────────── */
(function () {
  document.querySelectorAll('select[onchange]').forEach(function (sel) {
    sel.addEventListener('change', function () {
      var form = this.form;
      if (!form) return;
      form.classList.add('is-loading');
      var submits = form.querySelectorAll('select, button[type="submit"]');
      submits.forEach(function (el) { el.disabled = true; });
    });
  });
})();

/* ── 6b. Search date range validation ───────────────────────────────────── */
(function () {
  var from = document.getElementById('search-from');
  var to = document.getElementById('search-to');
  var err = document.getElementById('date-range-error');
  var form = document.getElementById('search-form');
  if (!from || !to || !form) return;

  function validateDates() {
    if (from.value && to.value && from.value > to.value) {
      err.hidden = false;
      from.classList.add('input-error');
      to.classList.add('input-error');
      return false;
    }
    err.hidden = true;
    from.classList.remove('input-error');
    to.classList.remove('input-error');
    return true;
  }

  from.addEventListener('change', validateDates);
  to.addEventListener('change', validateDates);
  form.addEventListener('submit', function (e) {
    if (!validateDates()) e.preventDefault();
  });
})();

/* ── 7. Disable submit buttons on form submit ───────────────────────────── */
(function () {
  // Prevent double-submissions by disabling the submit button once clicked.
  // Skips forms with [data-no-disable] (e.g. search forms that re-submit).
  document.querySelectorAll('form:not([data-no-disable])').forEach(function (form) {
    form.addEventListener('submit', function () {
      // Do not disable if the form has invalid HTML5 fields — the browser
      // will block the native submission and the button would be locked
      // permanently for the rest of the page session (bug fix).
      if (!form.checkValidity()) return;
      var submit = form.querySelector('button[type="submit"]:not([data-no-disable])');
      if (submit && !submit.disabled) {
        // Apply loading text from data-loading-text if present.
        var loadingText = submit.getAttribute('data-loading-text');
        if (loadingText) {
          submit.setAttribute('data-original-text', submit.textContent);
          submit.textContent = loadingText;
        }
        submit.disabled = true;
      }
    });
  });
})();

/* ── 8. Site alert dismiss ─────────────────────────────────────────────── */
(function () {
  var banner = document.getElementById('site-alert');
  var closeBtn = document.getElementById('site-alert-close');
  if (!banner || !closeBtn) return;

  closeBtn.addEventListener('click', function () {
    var id = banner.getAttribute('data-alert-id');
    // Set cookie valid for 30 days so the banner stays dismissed.
    var expires = new Date(Date.now() + 30 * 864e5).toUTCString();
    document.cookie = 'alert_dismissed_' + id + '=1; expires=' + expires + '; path=/; SameSite=Lax';
    banner.remove();
  });
})();

/* ── 9. Auto-submit selects with data-auto-submit ─────────────────────── */
(function () {
  document.querySelectorAll('select[data-auto-submit]').forEach(function (sel) {
    sel.addEventListener('change', function () {
      var form = this.form;
      if (form) form.submit();
    });
  });
})();
