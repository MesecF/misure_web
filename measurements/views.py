from django.shortcuts import render
from django.views import View

from accounts.mixins import TenantRequiredMixin

from .entry import (EntryForm, elements_for, find_article, parse_employee_number, save_measurement,
                    todays_measurements)

SESSION_EMPLOYEE_NUMBER = 'employee_number'


class MeasurementEntryView(TenantRequiredMixin, View):
    """
    Entry page. The article panel (elements and today's measurements) is loaded
    with HTMX when a barcode is scanned and replaced after each save.
    """

    def get(self, request):
        return render(request, 'measurements/entry.html', {
            'employee_number': request.session.get(SESSION_EMPLOYEE_NUMBER, ''),
        })

    def post(self, request):
        employee_number, article, error, error_field = self.check_employee_and_article(request, request.POST)
        if error:
            return self.render_panel(request, error=error, error_field=error_field)
        elements = elements_for(article)
        form = EntryForm.from_post(elements, request.POST)
        if not form.is_valid:
            return self.render_panel(request, article=article, form=form)
        measurement = save_measurement(article, employee_number, form, request.user)
        # A new measurement starts right away for the same article and employee
        return self.render_panel(request, article=article, form=EntryForm(elements), saved=measurement)

    @staticmethod
    def check_employee_and_article(request, data):
        """
        Returns (employee_number, article, error, error_field); error_field is the input
        the cursor goes back to. A valid employee number is remembered for the session.
        """
        employee_number, error = parse_employee_number(data.get('employee_number'))
        if error:
            return None, None, error, 'employee_number'
        request.session[SESSION_EMPLOYEE_NUMBER] = employee_number
        article, error = find_article(request.tenant, data.get('barcode'))
        return employee_number, article, error, 'barcode' if error else ''

    @staticmethod
    def render_panel(request, article=None, form=None, error='', error_field='', saved=None):
        context = {'article': article, 'form': form, 'error': error, 'error_field': error_field, 'saved': saved}
        if article is not None:
            context['todays_measurements'] = todays_measurements(article, form.elements)
        return render(request, 'measurements/partials/article_panel.html', context)


class ArticlePanelView(MeasurementEntryView):
    """HTMX: panel for the scanned barcode."""

    http_method_names = ['get']

    def get(self, request):
        employee_number, article, error, error_field = self.check_employee_and_article(request, request.GET)
        if error:
            return self.render_panel(request, error=error, error_field=error_field)
        return self.render_panel(request, article=article, form=EntryForm(elements_for(article)))
