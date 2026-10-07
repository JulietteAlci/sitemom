from datetime import timedelta

from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from .models import GoldPrice


def gold_price_page(request):
    since = timezone.now() - timedelta(days=30)
    history = list(GoldPrice.objects.filter(fetched_at__gte=since).order_by("fetched_at"))
    # One point per day (last quote of the day) for the history table.
    daily = {}
    for quote in history:
        daily[timezone.localdate(quote.fetched_at)] = quote
    return render(
        request,
        "pricing/gold_price.html",
        {"daily_history": sorted(daily.items(), reverse=True)},
    )


def gold_price_api(request):
    quote = GoldPrice.current()
    if quote is None:
        return JsonResponse({"available": False}, status=503)
    return JsonResponse(
        {
            "available": True,
            "eur_per_oz": str(quote.price_per_oz_eur),
            "eur_per_gram_24k": f"{quote.price_per_gram_eur:.4f}",
            "fetched_at": quote.fetched_at.isoformat(),
            "fresh": quote.is_fresh,
        }
    )
