/**
 * Body mode toggle — switches between Write (Quill) and Upload Markdown modes.
 * Loaded as an external script (CSP-safe — no inline scripts allowed).
 */
(function () {
  var radios = document.querySelectorAll('input[name="_body_mode_ui"]');
  var modeInput = document.getElementById('body_mode');
  var writeSection = document.getElementById('body-write-section');
  var uploadSection = document.getElementById('body-upload-section');

  if (!modeInput || !writeSection || !uploadSection) return;

  function switchMode(mode) {
    modeInput.value = mode;
    if (mode === 'upload_md') {
      writeSection.style.display = 'none';
      uploadSection.style.display = '';
    } else {
      writeSection.style.display = '';
      uploadSection.style.display = 'none';
    }
  }

  radios.forEach(function (r) {
    r.addEventListener('change', function () {
      switchMode(this.value);
    });
  });

  // On form submit, if upload_md mode is active, clear the body textarea so
  // Quill's syncToTextarea handler (registered on DOMContentLoaded) does not
  // persist stale HTML into the body field.  Registered on 'load' so it fires
  // AFTER post-editor.js's DOMContentLoaded submit handler.
  window.addEventListener('load', function () {
    var form = modeInput ? modeInput.closest('form') : null;
    if (form) {
      form.addEventListener('submit', function () {
        if (modeInput.value === 'upload_md') {
          var textarea = document.getElementById('id_body');
          if (textarea) textarea.value = '';
        }
      });
    }
  });
})();
