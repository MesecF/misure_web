from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpResponse
from django.shortcuts import resolve_url


class DefaultLanguageMiddleware:
    """
    English is the default UI language regardless of browser settings; other
    languages are used only when chosen in the language switch (stored in a cookie).
    Must run before django.middleware.locale.LocaleMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.META.pop('HTTP_ACCEPT_LANGUAGE', None)
        return self.get_response(request)


class TenantMiddleware:
    """
    Sets request.tenant to the logged-in user's tenant (None for superadmins and
    anonymous users). Users of a deactivated tenant are logged out.
    Must run after AuthenticationMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = None
        user = request.user
        if user.is_authenticated and user.tenant_id:
            if user.tenant.is_active:
                request.tenant = user.tenant
            else:
                logout(request)
        return self.get_response(request)


class HtmxLoginRedirectMiddleware:
    """
    When the session has ended, LoginRequiredMiddleware answers an HTMX request with a redirect
    to the login page; the browser would follow it and HTMX would put the login page into a
    part of the page. Instead the whole page goes to the login page (HX-Redirect), with the
    page the user was on as "next".
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        login_url = resolve_url(settings.LOGIN_URL)
        if (request.headers.get('HX-Request') and response.status_code == 302
                and response.get('Location', '').startswith(login_url)):
            page = urlsplit(request.headers.get('HX-Current-URL', '')).path or '/'
            redirect = HttpResponse(status=204)
            redirect['HX-Redirect'] = f'{login_url}?{urlencode({"next": page})}'
            return redirect
        return response
