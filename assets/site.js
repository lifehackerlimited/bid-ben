/* Bid Ben: the sign-up box, the "days left" on deadlines, and "last checked". No tracking and no cookies. */
(function () {
  'use strict';

  // Deadlines. The page carries the official date; this adds how long is left and greys out any that have passed,
  // so the page stays right between the daily rebuilds.
  function daysUntil(time) {
    var then = new Date(time), today = new Date();
    then.setHours(0, 0, 0, 0);
    today.setHours(0, 0, 0, 0);
    return Math.round((then - today) / 864e5);
  }
  document.querySelectorAll('[data-deadline]').forEach(function (el) {
    var time = Date.parse(el.getAttribute('data-deadline'));
    var left = el.querySelector('.left');
    if (isNaN(time) || !left) return;
    var days = daysUntil(time);
    if (time < Date.now()) {
      left.textContent = ' (closed)';
      var box = el.closest('.card, tr');
      if (box) box.classList.add('shut');
    } else {
      left.textContent = days === 0 ? ' (today)' : days === 1 ? ' (tomorrow)' : ' (' + days + ' days left)';
      if (days <= 7) left.className = 'left soon';
    }
  });

  // "Last checked": one small file the daily build updates, so pages don't all change every day.
  var checked = document.querySelectorAll('[data-checked]');
  if (checked.length && window.fetch) {
    fetch('/status.json', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (s) {
      if (!s || !s.checked) return;
      var d = new Date(s.checked + 'T12:00:00');
      var text = d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
      checked.forEach(function (el) { el.textContent = 'Last checked ' + text + '.'; });
    }).catch(function () {});
  }

  // Sign-up. Sends the form to our form service and stays on the page. If that fails, it offers a plain email
  // instead, so nobody who wants to sign up is turned away.
  document.querySelectorAll('form.js-signup').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      if (!window.fetch || !window.FormData) return;      // very old browser: let the form post normally
      e.preventDefault();
      var status = form.querySelector('.status');
      var button = form.querySelector('button');
      var email = form.querySelector('[name=email]').value.trim();
      var areas = (form.querySelector('[name=areas]') || {}).value || '';
      var data = new FormData(form);
      data.set('page', location.pathname);
      button.disabled = true;
      status.className = 'status';
      status.textContent = 'Signing you up…';
      fetch(form.action, { method: 'POST', body: data, headers: { Accept: 'application/json' } })
        .then(function (res) { if (!res.ok) throw new Error(String(res.status)); })
        .then(function () {
          form.querySelectorAll('label, button, .small').forEach(function (el) { el.hidden = true; });
          status.className = 'status ok';
          status.textContent = "You're on the list. A welcome email and the latest issue will reach " + email +
            ' on the next working morning, then a new issue every Monday.';
        })
        .catch(function () {
          button.disabled = false;
          var to = form.getAttribute('data-fallback');
          var link = document.createElement('a');
          link.href = 'mailto:' + to + '?subject=' + encodeURIComponent('Bid Ben sign-up') + '&body=' +
            encodeURIComponent('Please add me to Bid Ben.\n\nemail: ' + email + '\nareas: ' + areas + '\n');
          link.textContent = to;
          status.className = 'status bad';
          status.textContent = "Sorry, that didn't go through. Email ";
          status.appendChild(link);
          status.appendChild(document.createTextNode(" and we'll add you by hand."));
        });
    });
  });
})();
