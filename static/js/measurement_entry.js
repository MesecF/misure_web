// Measurement entry: keyboard flow for the barcode scanner and the measuring device.
// Both send Tab after each reading. Tab after the barcode loads the article's elements,
// Tab moves from element to element, and Tab after the last element asks to save.
// Enter behaves like Tab. F2 = new article, F3 = change employee.
(function () {
  const form = document.getElementById('entry-form');
  const employee = document.getElementById('employee_number');
  const barcode = document.getElementById('barcode');
  const panel = document.getElementById('article-panel');
  const modalElement = document.getElementById('confirm-modal');
  const modal = new bootstrap.Modal(modalElement);
  const summary = document.getElementById('confirm-summary');
  const emptyMessage = document.getElementById('confirm-empty');
  const saveButton = document.getElementById('confirm-save');
  const namesSwitch = document.getElementById('show-element-names');
  const message = document.getElementById('entry-message');
  const LABELS_KEY = 'misure.showElementNames';
  let saving = false;
  // A save request is on its way: no second save (Enter pressed again on a slow server)
  let busy = false;
  // Barcode of the article loaded or being loaded: the same barcode is not loaded twice in a row
  let loadedBarcode = '';

  // Element codes (default) or names; the choice is remembered in this browser
  function showElementNames(show) {
    form.classList.toggle('show-element-names', show);
    form.classList.toggle('show-element-codes', !show);
    namesSwitch.checked = show;
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
    // Back to where the employee was typing
    const inputs = elementInputs();
    focusAndSelect(inputs[0] || barcode);
  });

  function elementInputs() {
    return Array.from(panel.querySelectorAll('.element-input'));
  }

  function focusAndSelect(input) {
    if (input) {
      input.focus();
      input.select();
    }
  }

  function newArticle() {
    barcode.value = '';
    loadedBarcode = '';
    panel.replaceChildren();
    message.replaceChildren();
    barcode.focus();
  }

  function showError(text) {
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger fw-semibold';
    alert.textContent = text;
    message.replaceChildren(alert);
  }

  function changeEmployee() {
    employee.value = '';
    employee.focus();
  }

  function askToSave() {
    if (busy) {
      return;
    }
    const filled = elementInputs().filter((input) => input.value.trim() !== '');
    summary.replaceChildren(...filled.map((input) => {
      const row = document.createElement('tr');
      const label = document.createElement('th');
      label.textContent = namesSwitch.checked ? input.dataset.name : input.dataset.code;
      const value = document.createElement('td');
      value.className = 'text-end';
      value.textContent = `${input.value.trim()} ${input.dataset.unit}`;
      row.append(label, value);
      return row;
    }));
    emptyMessage.hidden = filled.length > 0;
    saveButton.disabled = filled.length === 0;
    modal.show();
  }

  document.getElementById('new-article').addEventListener('click', newArticle);
  document.getElementById('change-employee').addEventListener('click', changeEmployee);

  document.addEventListener('keydown', (event) => {
    if (modalElement.classList.contains('show')) {
      return;
    }
    if (event.key === 'F2') {
      event.preventDefault();
      newArticle();
    } else if (event.key === 'F3') {
      event.preventDefault();
      changeEmployee();
    }
  });

  form.addEventListener('keydown', (event) => {
    if ((event.key !== 'Tab' && event.key !== 'Enter') || event.shiftKey) {
      return;
    }
    const target = event.target;
    if (target === employee && event.key === 'Enter') {
      event.preventDefault();
      barcode.focus();
      return;
    }
    if (target === barcode && event.key === 'Enter') {
      // Tab triggers loading through the change event when the field is left;
      // Enter keeps the cursor here, so load explicitly
      event.preventDefault();
      htmx.trigger(barcode, 'change');
      return;
    }
    const inputs = elementInputs();
    const index = inputs.indexOf(target);
    if (index === -1) {
      return;
    }
    if (index === inputs.length - 1) {
      event.preventDefault();
      askToSave();
    } else if (event.key === 'Enter') {
      event.preventDefault();
      focusAndSelect(inputs[index + 1]);
    }
  });

  modalElement.addEventListener('shown.bs.modal', () => {
    if (!saveButton.disabled) {
      saveButton.focus();
    }
  });

  modalElement.addEventListener('hidden.bs.modal', () => {
    if (!saving) {
      // Back to the last element to correct values
      const inputs = elementInputs();
      focusAndSelect(inputs[inputs.length - 1]);
    }
    saving = false;
  });

  saveButton.addEventListener('click', () => {
    if (busy) {
      return;
    }
    saving = true;
    modal.hide();
    form.requestSubmit();
  });

  // After the panel is replaced: cursor to the field with the error, otherwise to the first element
  document.body.addEventListener('htmx:afterSwap', (event) => {
    if (event.detail.target !== panel) {
      return;
    }
    const errorField = panel.querySelector('[data-focus]');
    if (errorField && errorField.dataset.focus) {
      focusAndSelect(document.getElementById(errorField.dataset.focus));
      return;
    }
    const inputs = elementInputs();
    focusAndSelect(inputs.find((input) => input.classList.contains('is-invalid')) || inputs[0]);
  });

  document.body.addEventListener('htmx:beforeRequest', (event) => {
    const source = event.detail.elt;
    if (source === barcode) {
      // Enter loads explicitly; when the cursor then leaves the field, the browser reports
      // a change once more. That second load would wipe values typed in the meantime.
      if (barcode.value === loadedBarcode) {
        event.preventDefault();
        return;
      }
      loadedBarcode = barcode.value;
    } else if (source === form) {
      busy = true;
    }
  });

  document.body.addEventListener('htmx:afterRequest', (event) => {
    const source = event.detail.elt;
    if (source === form) {
      busy = false;
    }
    if (source !== form && source !== barcode) {
      return;
    }
    if (event.detail.successful) {
      message.replaceChildren();
    } else if (source === barcode) {
      // Not loaded: the same barcode can be tried again
      loadedBarcode = '';
    }
  });

  // Server error or no connection: the panel and the entered values stay, the message says what
  // was not done. A save that failed must not look like a successful one.
  function requestFailed(event, offline) {
    const source = event.detail.elt;
    if (source === form) {
      showError(offline ? message.dataset.saveOffline : message.dataset.saveError);
      const inputs = elementInputs();
      focusAndSelect(inputs[inputs.length - 1]);
    } else if (source === barcode) {
      showError(offline ? message.dataset.loadOffline : message.dataset.loadError);
    }
  }

  document.body.addEventListener('htmx:responseError', (event) => requestFailed(event, false));
  document.body.addEventListener('htmx:sendError', (event) => requestFailed(event, true));
})();
