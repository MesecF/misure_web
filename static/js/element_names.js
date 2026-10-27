// "Show element names" switch on pages without the entry form: shows element codes (default)
// or names in the element with id data-target. Same remembered choice as on the entry page.
// Links marked data-element-labels (exports) get labels=codes|names, so the file matches the screen.
(function () {
  const target = document.getElementById(document.currentScript.dataset.target);
  const namesSwitch = document.getElementById('show-element-names');
  const LABELS_KEY = 'misure.showElementNames';
  if (!target || !namesSwitch) {
    return;
  }

  function showElementNames(show) {
    target.classList.toggle('show-element-names', show);
    target.classList.toggle('show-element-codes', !show);
    namesSwitch.checked = show;
    document.querySelectorAll('a[data-element-labels]').forEach((link) => {
      const url = new URL(link.href);
      url.searchParams.set('labels', show ? 'names' : 'codes');
      link.href = url.toString();
    });
  }

  try {
    showElementNames(localStorage.getItem(LABELS_KEY) === '1');
  } catch (error) {
    showElementNames(false);
  }

  namesSwitch.addEventListener('change', () => {
    showElementNames(namesSwitch.checked);
    try {
      localStorage.setItem(LABELS_KEY, namesSwitch.checked ? '1' : '0');
    } catch (error) {
      // Not remembered, but the switch still works for this page
    }
  });
})();
