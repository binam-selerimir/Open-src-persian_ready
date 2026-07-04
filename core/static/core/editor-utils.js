/**
 * core/static/core/editor-utils.js
 * ================================
 * Shared utilities for Quill.js rich-text editors.
 * Used by both post-editor.js (admin) and forum-editor.js (forum).
 *
 * Provides:
 * - getCsrfToken()     – CSRF token from hidden form input
 * - escapeHtml()       – XSS-safe HTML escaping
 * - uploadMedia()      – File upload with progress callback
 * - buildMediaHtml()   – HTML snippet for uploaded media
 * - insertMediaHtml()  – Insert HTML into Quill at cursor
 */

(function () {
  'use strict';

  function getCsrfToken() {
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function uploadMedia(file, uploadUrl, onProgress, timeout) {
    var formData = new FormData();
    formData.append('file', file);
    var msgs = window.EditorMessages || {};
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      xhr.open('POST', uploadUrl);
      xhr.setRequestHeader('X-CSRFToken', getCsrfToken());
      xhr.credentials = 'same-origin';
      var timer = null;
      if (timeout) {
        timer = setTimeout(function () {
          xhr.abort();
          reject(new Error(msgs.uploadTimeout || 'Upload timed out.'));
        }, timeout);
      }
      if (onProgress) {
        xhr.upload.addEventListener('progress', function (e) {
          if (e.lengthComputable) onProgress({ loaded: e.loaded, total: e.total });
        });
      }
      xhr.addEventListener('load', function () {
        if (timer) clearTimeout(timer);
        try {
          var data = JSON.parse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300) resolve(data);
          else reject(new Error(data.error || msgs.uploadFailed || 'Upload failed.'));
        } catch (_) { reject(new Error(msgs.uploadFailed || 'Upload failed.')); }
      });
      xhr.addEventListener('error', function () {
        if (timer) clearTimeout(timer);
        reject(new Error(msgs.uploadFailed || 'Upload failed.'));
      });
      xhr.addEventListener('abort', function () {
        if (timer) clearTimeout(timer);
        reject(new Error(msgs.uploadCancelled || 'Upload cancelled.'));
      });
      xhr.send(formData);
    });
  }

  function buildMediaHtml(data) {
    var url  = escapeHtml(data.url  || '');
    var name = escapeHtml(data.name || '');
    var cap  = name ? '<figcaption class="media-caption">' + name + '</figcaption>' : '';
    var pcap = name ? '<p class="media-caption">' + name + '</p>' : '';

    switch (data.type) {
      case 'image':
        return '<figure class="media-embed media-embed--image">' +
          '<img src="' + url + '" alt="' + name + '" loading="lazy">' +
          cap + '</figure><p><br></p>';
      case 'video':
        return '<div class="media-embed media-embed--video">' +
          '<video controls preload="metadata" src="' + url + '"></video>' +
          pcap + '</div><p><br></p>';
      case 'audio':
        return '<div class="media-embed media-embed--audio">' +
          '<audio controls preload="metadata" src="' + url + '"></audio>' +
          pcap + '</div><p><br></p>';
      default:
        return '<p><a href="' + url + '">' + name + '</a></p>';
    }
  }

  function insertMediaHtml(quill, html) {
    var range = quill.getSelection(true);
    var index = range ? range.index : quill.getLength();
    quill.clipboard.dangerouslyPasteHTML(index, html);
    var temp = document.createElement('div');
    temp.innerHTML = html;
    var len = temp.textContent.length || 1;
    quill.setSelection(index + len);
  }

  window.EditorUtils = {
    getCsrfToken: getCsrfToken,
    escapeHtml: escapeHtml,
    uploadMedia: uploadMedia,
    buildMediaHtml: buildMediaHtml,
    insertMediaHtml: insertMediaHtml,
  };
})();
