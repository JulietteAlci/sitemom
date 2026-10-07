from .models import GoldPrice


def gold_price(request):
    return {"gold_spot": GoldPrice.current()}
