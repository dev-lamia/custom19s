/** Ensure the hidden redirect form exists on every website page. No deps. */
odoo.define('@test/js/bkash_redirect', function () {
  'use strict';

  function ensureForm() {
    if (!document.getElementById('o_payment_redirect_form')) {
      const f = document.createElement('form');
      f.id = 'o_payment_redirect_form';
      f.method = 'get';
      f.style.display = 'none';
      document.body.appendChild(f);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ensureForm, { once: true });
  } else {
    ensureForm();
  }
});
