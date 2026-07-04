/**
 * core/static/core/post-editor.js
 * ================================
 * WYSIWYG rich-text post editor for the admin panel.
 * Loaded by accounts/templates/accounts/_post_editor_scripts.html.
 *
 * Integrations
 * ------------
 * Quill     – rich-text editor (toolbar + HTML output).
 * TomSelect – searchable multi-select for the tags field.
 *
 * Features
 * --------
 * 1. initRichText()    – mounts a Quill editor over the hidden #id_body textarea,
 *                        keeping both in sync so the Django form always submits HTML.
 * 2. initMediaToolbar() – binds toolbar image/video/audio buttons and the drag-and-
 *                         drop zone to the upload endpoint, then inserts the returned
 *                         URL as an HTML media element into the editor.
 * 3. initTagSelect()   – mounts TomSelect on #id_tags for searchable multi-select.
 * 4. initFilePreviews() – generic inline file preview for [data-file-preview] widgets.
 * 5. initCoverUpload() – drag-and-drop cover image picker with live preview.
 *
 * Security notes
 * --------------
 * * getCsrfToken() reads the CSRF token from the hidden form input (or cookie
 *   fallback) and includes it in all AJAX upload requests.
 * * escapeHtml() is applied to all user-controlled values (filenames, URLs)
 *   before they are inserted into innerHTML to prevent XSS.
 * * Uploads are sent to /panel/upload-media/ which validates extension, file
 *   size, MIME type, and image integrity server-side.
 * * The script has no hardcoded English strings for translatable UI text; those
 *   are read from data-* attributes set by the Django template via {% trans %}.
 */

(function () {
  'use strict';

  /* ── Helpers (using shared EditorUtils) ──────────────────────────────── */

  var EU = window.EditorUtils;

  /**
   * Return the media upload URL from the quill editor container's data-upload-url
   * attribute, set by the Django template to /panel/upload-media/.
   */
  function getUploadUrl() {
    var el = document.getElementById('quill-editor');
    return el ? el.dataset.uploadUrl : '';
  }

  /**
   * Update the media upload status indicator element.
   * @param {HTMLElement} el       – the status element.
   * @param {string}      text     – message to display.
   * @param {string}      modifiers – extra CSS class(es) for state (busy/error).
   */
  function setStatus(el, text, modifiers) {
    if (!el) return;
    el.textContent = text;
    el.className = 'media-upload-status' + (modifiers ? ' ' + modifiers : '');
  }

  /**
   * Upload an array of files, showing a status message while pending,
   * and insert each result into the Quill editor.
   */
  function handleMediaFiles(quill, files, statusEl) {
    var list = Array.prototype.slice.call(files);
    if (!list.length) return;

    var pending = list.length;
    var container = document.getElementById('quill-editor');
    var uploadingText = (container && container.dataset.uploadingText)
      ? container.dataset.uploadingText.replace('{n}', pending)
      : 'Uploading ' + pending + ' file(s)\u2026';
    setStatus(statusEl, uploadingText, 'media-upload-status--busy');

    list.forEach(function (file) {
      EU.uploadMedia(file, getUploadUrl(), function (progress) {
        if (progress.total > 0) {
          var pct = Math.round((progress.loaded / progress.total) * 100);
          var label = uploadingText.replace(/\u2026$/, '') + ' ' + pct + '%';
          setStatus(statusEl, label, 'media-upload-status--busy');
        }
      })
        .then(function (data) {
          EU.insertMediaHtml(quill, EU.buildMediaHtml(data));
        })
        .catch(function (err) {
          setStatus(statusEl, err.message || 'Upload failed.', 'media-upload-status--error');
        })
        .finally(function () {
          pending -= 1;
          if (pending === 0 && statusEl && !statusEl.classList.contains('media-upload-status--error')) {
            setStatus(statusEl, '');
          }
        });
    });
  }

  /* ── Media toolbar ────────────────────────────────────────────────────── */

  /**
   * Bind the Quill toolbar media buttons and the drag-and-drop zone to the
   * upload handler.  Replaces Quill's default image handler with one that
   * sends files to our server endpoint instead of embedding base64 data URIs.
   */
  function initMediaToolbar(quill) {
    var toolbar  = quill.getModule('toolbar');
    if (!toolbar) return;

    var statusEl  = document.getElementById('media-upload-status');
    var fileInput = document.getElementById('post-media-file-input');
    var dropZone  = document.getElementById('post-media-dropzone');

    /** Open the system file picker with the given MIME type filter. */
    function openFilePicker(accept) {
      if (!fileInput) return;
      fileInput.accept = accept;
      fileInput.value  = '';     // Reset so re-selecting the same file fires 'change'.
      fileInput.click();
    }

    /** Bind a toolbar button (found by CSS selector) to open the file picker. */
    function bindBtn(selector, accept) {
      var btn = document.querySelector(selector);
      if (btn) btn.addEventListener('click', function (e) {
        e.preventDefault();
        openFilePicker(accept);
      });
    }

    // Override Quill's default image handler to use our upload endpoint.
    toolbar.addHandler('image', function () {
      openFilePicker('image/jpeg,image/png,image/gif,image/webp');
    });
    bindBtn('.ql-video', 'video/mp4,video/webm,video/ogg,video/quicktime');
    bindBtn('.ql-audio', 'audio/mpeg,audio/ogg,audio/wav,audio/mp4,audio/flac,audio/aac');

    if (fileInput) {
      fileInput.addEventListener('change', function () {
        handleMediaFiles(quill, fileInput.files, statusEl);
      });
    }

    // Bind the media drop zone for drag-and-drop uploads.
    if (dropZone) {
      bindDragDrop(dropZone, {
        onActive:   function () { dropZone.classList.add('media-dropzone--active'); },
        onInactive: function () { dropZone.classList.remove('media-dropzone--active'); },
        onDrop:     function (e) { handleMediaFiles(quill, e.dataTransfer.files, statusEl); },
        onClick:    function () { openFilePicker('image/*,video/*,audio/*'); },
      });
    }
  }

  /* ── Drag-and-drop helper ─────────────────────────────────────────────── */

  /**
   * Attach drag-and-drop event listeners to an element.
   * @param {HTMLElement} el – the drop target.
   * @param {Object} handlers – callbacks: onActive, onInactive, onDrop, onClick.
   */
  function bindDragDrop(el, handlers) {
    // Show active state while a dragged item hovers over the element.
    ['dragenter', 'dragover'].forEach(function (evt) {
      el.addEventListener(evt, function (e) { e.preventDefault(); handlers.onActive(); });
    });
    // Remove active state when the drag leaves or the drop completes.
    ['dragleave', 'drop'].forEach(function (evt) {
      el.addEventListener(evt, function (e) { e.preventDefault(); handlers.onInactive(); });
    });
    if (handlers.onDrop)  el.addEventListener('drop',  handlers.onDrop);
    if (handlers.onClick) el.addEventListener('click', handlers.onClick);
  }

  /* ── 1. Rich text editor (Quill) ─────────────────────────────────────── */

  /**
   * Mount the Quill editor over the hidden #id_body textarea.
   * On every text change, the textarea value is updated so the standard
   * Django form submit always includes the current editor HTML.
   */
  function initRichText() {
    var textarea  = document.getElementById('id_body');
    var container = document.getElementById('quill-editor');
    if (!textarea || !container || typeof Quill === 'undefined') return;

    // Hide the raw textarea — Quill's visual editor replaces it.
    textarea.classList.add('richtext-source--hidden');

    var quill = new Quill(container, {
      theme: 'snow',
      modules: {
        toolbar: {
          container: [
            ['bold', 'italic', 'underline'],
            ['link', 'code-block'],
            [{ header: [2, 3, false] }],
            [{ list: 'ordered' }, { list: 'bullet' }],
            ['blockquote'],
            // Direction toggle (RTL ⇌ LTR).  Quill's bundled quill.snow.css
            // already provides .ql-direction-rtl { direction: rtl; text-align:
            // inherit } and the SVG icon swap logic — all we need is the
            // toolbar button and the handler below.
            [{ direction: 'rtl' }],
            // Text-align dropdown.  Works together with the direction handler:
            // clicking the direction button automatically sets/clears align
            // so the user only needs one click for proper Persian paragraphs.
            [{ align: [] }],
            ['image', 'video', 'audio'],    // Custom upload buttons.
            ['clean'],                       // Strip all formatting.
          ],
          handlers: {
            video: function () {},
            audio: function () {},
            /**
             * Custom direction handler.
             *
             * Quill's default direction handler only sets `direction: rtl`
             * on the paragraph-level attribute.  But .ql-editor itself is
             * hardcoded to `text-align: left` in quill.snow.css (our
             * post-editor.css overrides this to `text-align: start` to
             * lessen the conflict, but `inherit` still resolves to `start`
             * → left for LTR paragraphs inside the editor).
             *
             * For a Persian (RTL) paragraph to look correct, both must be
             * set together: direction → rtl AND align → right.  Toggling
             * back to LTR (direction → false) resets align to '' (default).
             *
             * This single-click behaviour matches what the Quill docs and
             * the Arabic/Persian community recommend (see slab/quill#127).
             */
            direction: function (value) {
              if (value === 'rtl') {
                this.quill.format('direction', 'rtl', 'user');
                this.quill.format('align', 'right', 'user');
              } else {
                this.quill.format('direction', false, 'user');
                this.quill.format('align', false, 'user');
              }
            },
          },
        },
      },
      placeholder: container.dataset.placeholder || '',
    });

    // Pre-populate the editor with the existing body when editing a post.
    if (textarea.value) quill.root.innerHTML = textarea.value;

    /** Keep the textarea in sync with the editor so the form can submit it. */
    function syncToTextarea() {
      var html = quill.root.innerHTML;
      // Quill's empty-editor placeholder is '<p><br></p>'; treat that as empty.
      textarea.value = html === '<p><br></p>' ? '' : html;
    }

    quill.on('text-change', syncToTextarea);

    // Also sync on form submit in case the text-change event was missed.
    var form = textarea.closest('form');
    if (form) form.addEventListener('submit', syncToTextarea);

    initMediaToolbar(quill);
  }

  /* ── 2. Tag select (TomSelect) ───────────────────────────────────────── */

  /**
   * Upgrade the #id_tags <select multiple> with TomSelect for
   * searchable, keyboard-navigable multi-select with remove buttons.
   */
  function initTagSelect() {
    var el = document.getElementById('id_tags');
    if (!el || typeof TomSelect === 'undefined' || el.tomselect) return;

    new TomSelect(el, {
      plugins: ['remove_button'],       // Shows an × on each selected tag chip.
      maxItems: null,                   // Allow selecting unlimited tags.
      placeholder: el.dataset.placeholder || 'Search tags\u2026',
      allowEmptyOption: true,
      closeAfterSelect: false,          // Keep the dropdown open for multi-select.
      hideSelected: false,
      render: {
        no_results: function () {
          var text = (el.dataset.noTagsText) || 'No tags found';
          return '<div class="no-results">' + text + '</div>';
        },
      },
    });
  }

  /* ── 3. Generic file previews ────────────────────────────────────────── */

  /**
   * Bind a live file preview to any [data-file-preview] wrapper that contains
   * an <input type="file"> and a [data-preview-target] container.
   * Shows an <img> preview for image files, or the filename for other types.
   */
  function initFilePreviews() {
    document.querySelectorAll('[data-file-preview]').forEach(function (wrap) {
      var input   = wrap.querySelector('input[type="file"]');
      var preview = wrap.querySelector('[data-preview-target]');
      if (!input || !preview) return;

      input.addEventListener('change', function () {
        var file = input.files && input.files[0];
        if (!file) return;
        if (file.type.startsWith('image/')) {
          // Read the file as a data URL for immediate local preview.
          var reader = new FileReader();
          reader.onload = function (e) {
            preview.innerHTML = '<img src="' + e.target.result + '" alt="" class="file-preview-img">';
          };
          reader.readAsDataURL(file);
        } else {
          // Non-image: just show the filename.
          preview.innerHTML = '<span class="file-preview-name">' + EU.escapeHtml(file.name) + '</span>';
        }
      });
    });
  }

  /* ── 4. Cover image upload ───────────────────────────────────────────── */

  // Static placeholder HTML shown before a cover image is selected.
  var editorEl = document.getElementById('quill-editor');
  var coverTitle = (editorEl && editorEl.dataset.coverTitle) || 'Add a cover image';
  var coverHint = (editorEl && editorEl.dataset.coverHint) || 'Drag & drop here, or click to browse';
  var coverFormats = (editorEl && editorEl.dataset.coverFormats) || 'JPG \u00b7 PNG \u00b7 GIF \u00b7 WebP';
  var COVER_PLACEHOLDER_HTML =
    '<div class="cover-upload-placeholder">' +
    '<span class="cover-upload-icon" aria-hidden="true">' +
    '<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">' +
    '<rect x="3" y="5" width="18" height="14" rx="2"/>' +
    '<circle cx="8.5" cy="10" r="1.5"/>' +
    '<path d="M21 16l-5.5-5.5a1 1 0 0 0-1.4 0L9 16"/>' +
    '</svg></span>' +
    '<span class="cover-upload-title">' + coverTitle + '</span>' +
    '<span class="cover-upload-hint">' + coverHint + '</span>' +
    '<span class="cover-upload-formats">' + coverFormats + '</span>' +
    '</div>';

  /**
   * Initialise the drag-and-drop cover image picker.
   * Reads the selected image client-side for an immediate preview without
   * uploading.  The actual file upload happens on form submit.
   */
  function initCoverUpload() {
    var card = document.querySelector('[data-cover-upload]');
    if (!card) return;

    var input     = card.querySelector('.cover-file-input, #id_cover_image');
    var preview   = card.querySelector('[data-cover-preview]');
    var dropzone  = card.querySelector('[data-cover-dropzone]');
    var overlay   = card.querySelector('[data-cover-overlay]');
    var chooseBtn = card.querySelector('[data-cover-choose]');
    var removeBtn = card.querySelector('[data-cover-remove]');

    if (!input || !preview) return;

    /** Render an image preview from a base64 data URL. */
    function showPreview(src) {
      preview.innerHTML = '<img src="' + src + '" alt="" class="cover-upload-img">';
      if (overlay)    overlay.hidden    = false;
      if (removeBtn)  removeBtn.hidden  = false;
    }

    /** Restore the empty placeholder state. */
    function showPlaceholder() {
      preview.innerHTML = COVER_PLACEHOLDER_HTML;
      if (overlay)    overlay.hidden    = true;
      if (removeBtn)  removeBtn.hidden  = true;
    }

    /**
     * Handle a dropped or selected image file:
     * - Validates it is an image (by MIME prefix).
     * - Assigns it to the file input (DataTransfer trick) so it submits with the form.
     * - Reads it with FileReader for an immediate local preview.
     */
    function handleFile(file) {
      if (!file || !file.type.startsWith('image/')) return;
      // Assign the dropped file to the input element so the form includes it.
      var dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
      var reader = new FileReader();
      reader.onload = function (e) { showPreview(e.target.result); };
      reader.readAsDataURL(file);
    }

    function openPicker() { input.click(); }

    input.addEventListener('change', function () {
      if (input.files && input.files[0]) handleFile(input.files[0]);
    });

    if (chooseBtn) chooseBtn.addEventListener('click', openPicker);

    if (dropzone) {
      bindDragDrop(dropzone, {
        onActive:   function () { dropzone.classList.add('cover-upload-dropzone--active'); },
        onInactive: function () { dropzone.classList.remove('cover-upload-dropzone--active'); },
        onDrop:     function (e) { handleFile(e.dataTransfer.files && e.dataTransfer.files[0]); },
        onClick:    openPicker,
      });
      // Allow keyboard users to activate the dropzone with Enter or Space.
      dropzone.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPicker(); }
      });
    }

    // Clear the cover image and reset the placeholder when "Remove" is clicked.
    if (removeBtn) removeBtn.addEventListener('click', function () {
      input.value = '';
      showPlaceholder();
    });
  }

  /* ── Boot ─────────────────────────────────────────────────────────────── */

  document.addEventListener('DOMContentLoaded', function () {
    initRichText();
    initTagSelect();
    initFilePreviews();
    initCoverUpload();
  });
})();
