from django.conf import settings


def site(request):
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_URL": settings.SITE_URL,
        "canonical_url": settings.SITE_URL + request.path,
        "TRIAL_KIT_MIN": settings.TRIAL_KIT_MIN,
        "TRIAL_KIT_MAX": settings.TRIAL_KIT_MAX,
        "STRIPE_DEMO_MODE": settings.STRIPE_DEMO_MODE,
        "TRIAL_KIT_PRICE": settings.TRIAL_KIT_PRICE_CENTS // 100,
    }
