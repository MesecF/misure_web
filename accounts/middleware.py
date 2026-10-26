from django.contrib.auth import logout


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
