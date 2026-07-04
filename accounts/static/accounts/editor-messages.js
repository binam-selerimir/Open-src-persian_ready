/**
 * Editor messages — reads translated strings from data-* attributes on
 * #editor-config and exposes them as window.EditorMessages for editors.
 * CSP-safe: no inline scripts needed.
 */
(function () {
  var el = document.getElementById('editor-config');
  if (el) {
    window.EditorMessages = {
      uploadFailed: el.getAttribute('data-upload-failed') || 'Upload failed.',
      uploadCancelled: el.getAttribute('data-upload-cancelled') || 'Upload cancelled.',
      uploading: el.getAttribute('data-uploading') || 'Uploading',
      uploadTimeout: el.getAttribute('data-upload-timeout') || 'Upload timed out.',
      editorLoadFailed: el.getAttribute('data-editor-load-failed') || 'Rich text editor could not be loaded. You can still type plain text in the box below.'
    };
  }
})();
