from django.utils.translation import get_language
from django.views.generic import TemplateView

from accounts.mixins import TenantRequiredMixin


class HomeView(TenantRequiredMixin, TemplateView):
    template_name = 'home.html'


class HelpView(TenantRequiredMixin, TemplateView):
    """
    User guide in the UI language. Each language has its own text (templates/help/content_<language>.html),
    long texts are easier to write and correct there than in the translation files.
    """

    template_name = 'help/help.html'
    LANGUAGES = ('en', 'hr', 'it')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language = get_language()
        context['content_template'] = f"help/content_{language if language in self.LANGUAGES else 'en'}.html"
        return context
