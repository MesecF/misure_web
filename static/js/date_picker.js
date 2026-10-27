// Date fields (.date-picker): the server gets yyyy-mm-dd, the user sees and types the date
// in the format of the UI language (data-date-format on this script, Django's SHORT_DATE_FORMAT).
(function () {
  const displayFormat = document.currentScript.dataset.dateFormat || 'd/m/Y';
  const language = document.documentElement.lang;

  document.querySelectorAll('.date-picker').forEach((input) => {
    flatpickr(input, {
      dateFormat: 'Y-m-d',
      altInput: true,
      altFormat: displayFormat,
      allowInput: true,
      // Without this, phones show the browser's own date field in the browser's format
      disableMobile: true,
      locale: Object.assign({}, flatpickr.l10ns[language] || flatpickr.l10ns.default, {firstDayOfWeek: 1}),
    });
  });
})();
