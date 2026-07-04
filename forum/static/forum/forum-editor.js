/**
 * forum/static/forum/forum-editor.js
 * =====================================
 * Quill.js rich-text editor for forum reply/new-thread/edit-post forms.
 * Handles toolbar init, media upload, and textarea sync.
 *
 * Uses shared EditorUtils from core/static/core/editor-utils.js
 * for getCsrfToken, escapeHtml, uploadMedia, buildMediaHtml, insertMediaHtml.
 *
 * i18n strings are read from data attributes on the editor container
 * and from window.EditorMessages (set by templates via data attributes).
 */
(function () {
  'use strict';

  function getMsg(key, fallback) {
    if (window.EditorMessages && window.EditorMessages[key]) {
      return window.EditorMessages[key];
    }
    return fallback;
  }

  function initForumEditor(containerId, textareaId, uploadUrl) {
    var textarea  = document.getElementById(textareaId);
    var container = document.getElementById(containerId);
    if (!textarea || !container || typeof Quill === 'undefined') {
      if (container && typeof Quill === 'undefined') {
        container.innerHTML = '<p style="color:var(--text-muted);padding:1rem;">' +
          getMsg('editorLoadFailed', 'Rich text editor could not be loaded. You can still type plain text in the box below.') + '</p>';
        textarea.classList.remove('richtext-source--hidden');
      }
      return;
    }

    textarea.classList.add('richtext-source--hidden');

    var quill = new Quill(container, {
      theme: 'snow',
      modules: {
        toolbar: [
          ['bold', 'italic', 'underline'],
          ['link', 'code-block'],
          [{ header: [2, 3, false] }],
          [{ list: 'ordered' }, { list: 'bullet' }],
          ['blockquote'],
          [{ direction: 'rtl' }],
          [{ align: [] }],
          ['image'],
          ['clean'],
        ],
      },
      placeholder: container.dataset.placeholder || '',
    });

    if (textarea.value) quill.root.innerHTML = textarea.value;

    function syncToTextarea() {
      var html = quill.root.innerHTML;
      textarea.value = html === '<p><br></p>' ? '' : html;
      updateCharCount();
    }

    var MAX_BODY = 500000;
    var charCountEl = null;
    var editorWrap = container.closest('.richtext-editor-wrap');
    if (editorWrap) {
      charCountEl = document.createElement('div');
      charCountEl.className = 'form-char-count';
      editorWrap.appendChild(charCountEl);
    }
    function updateCharCount() {
      if (!charCountEl) return;
      var len = textarea.value.length;
      var warn = len >= MAX_BODY * 0.9;
      charCountEl.textContent = len.toLocaleString() + ' / ' + MAX_BODY.toLocaleString() + ' characters';
      charCountEl.classList.toggle('form-char-count--warn', warn);
    }
    updateCharCount();

    quill.on('text-change', syncToTextarea);

    var form = textarea.closest('form');
    if (form) form.addEventListener('submit', syncToTextarea);

    var toolbar = quill.getModule('toolbar');
    if (!toolbar) return;

    var fileInput = document.getElementById(containerId + '-file-input');

    toolbar.addHandler('image', function () {
      if (!fileInput) return;
      fileInput.value = '';
      fileInput.click();
    });

    var uploadStatus = null;
    if (editorWrap) {
      uploadStatus = document.createElement('div');
      uploadStatus.className = 'media-upload-status';
      editorWrap.appendChild(uploadStatus);
    }

    function setStatus(text, cls) {
      if (!uploadStatus) return;
      uploadStatus.textContent = text;
      uploadStatus.className = 'media-upload-status' + (cls ? ' ' + cls : '');
    }

    if (fileInput) {
      fileInput.addEventListener('change', function () {
        var list = Array.prototype.slice.call(fileInput.files);
        if (!list.length) return;
        var pending = list.length;
        var hasError = false;
        var uploadingMsg = getMsg('uploading', 'Uploading');
        setStatus(uploadingMsg + ' ' + pending + ' file(s)\u2026', 'media-upload-status--busy');
        list.forEach(function (file) {
          window.EditorUtils.uploadMedia(file, uploadUrl, function (progress) {
            if (progress.total > 0) {
              var pct = Math.round((progress.loaded / progress.total) * 100);
              setStatus(uploadingMsg + '\u2026 ' + pct + '%', 'media-upload-status--busy');
            }
          }, 30000)
            .then(function (data) { window.EditorUtils.insertMediaHtml(quill, window.EditorUtils.buildMediaHtml(data)); })
            .catch(function () { hasError = true; setStatus(getMsg('uploadFailed', 'Upload failed.'), 'media-upload-status--error'); })
            .finally(function () {
              pending -= 1;
              if (pending === 0 && uploadStatus) {
                if (hasError) {
                  setTimeout(function () { setStatus(''); }, 3000);
                } else {
                  setStatus('');
                }
              }
            });
        });
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var containers = document.querySelectorAll('[data-forum-editor]');
    containers.forEach(function (el) {
      initForumEditor(
        el.id,
        el.dataset.textareaId,
        el.dataset.uploadUrl
      );
    });
  });
})();
