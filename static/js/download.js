// Export links (a[data-download]): the file is fetched in the background while the button shows
// a spinner, then saved like a normal download. Errors are shown in #download-message.
// Texts come from this script's data-busy-text and data-error-text (translated in the template).
(function () {
  const texts = document.currentScript.dataset;
  const message = document.getElementById('download-message');

  function filenameFrom(response) {
    const match = /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') || '');
    return match ? match[1] : 'export';
  }

  function showError() {
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger';
    alert.textContent = texts.errorText;
    message.replaceChildren(alert);
  }

  document.querySelectorAll('a[data-download]').forEach((link) => {
    link.addEventListener('click', async (event) => {
      event.preventDefault();
      if (link.classList.contains('disabled')) {
        return;
      }
      const label = link.innerHTML;
      const spinner = document.createElement('span');
      spinner.className = 'spinner-border spinner-border-sm me-2';
      spinner.setAttribute('aria-hidden', 'true');
      link.replaceChildren(spinner, texts.busyText);
      link.classList.add('disabled');
      link.setAttribute('aria-disabled', 'true');
      message.replaceChildren();
      try {
        const response = await fetch(link.href, {credentials: 'same-origin'});
        if (response.redirected) {
          // No file but a page: the login page (session expired) or the list with a message
          // (e.g. date range too long for an export)
          window.location.href = response.url;
          return;
        }
        if (!response.ok) {
          throw new Error(response.statusText);
        }
        const url = URL.createObjectURL(await response.blob());
        const save = document.createElement('a');
        save.href = url;
        save.download = filenameFrom(response);
        document.body.append(save);
        save.click();
        save.remove();
        setTimeout(() => URL.revokeObjectURL(url), 10000);
      } catch (error) {
        showError();
      } finally {
        link.innerHTML = label;
        link.classList.remove('disabled');
        link.removeAttribute('aria-disabled');
      }
    });
  });
})();
