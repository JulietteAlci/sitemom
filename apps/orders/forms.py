from django import forms

from .cart import MAX_QUANTITY
from .payments import SHIPPING_COUNTRIES


class AddToCartForm(forms.Form):
    size = forms.TypedChoiceField(label="Taille (tour de doigt)", coerce=int)
    engraving = forms.CharField(
        label="Gravure intérieure (offerte)",
        max_length=40,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ex. : J & M — 12.06.2027"}),
    )
    quantity = forms.TypedChoiceField(
        label="Quantité", coerce=int, choices=[(i, i) for i in range(1, MAX_QUANTITY + 1)], initial=1
    )

    def __init__(self, *args, ring, **kwargs):
        super().__init__(*args, **kwargs)
        self.ring = ring
        self.fields["size"].choices = [(s, s) for s in ring.sizes]
        # Changing the size reloads the page with the matching price (see site.js).
        self.fields["size"].widget.attrs["data-price-preview"] = "taille"
        if not ring.engravable:
            del self.fields["engraving"]

    def clean_engraving(self):
        return self.cleaned_data.get("engraving", "").strip()


COUNTRY_NAMES = {"FR": "France", "BE": "Belgique", "LU": "Luxembourg", "CH": "Suisse", "MC": "Monaco"}


class DemoCheckoutForm(forms.Form):
    """Customer details collected by the simulated Stripe Checkout page (demo mode)."""

    email = forms.EmailField(label="E-mail")
    name = forms.CharField(label="Nom complet", max_length=200)
    phone = forms.CharField(label="Téléphone", max_length=40, required=False)
    line1 = forms.CharField(label="Adresse", max_length=200)
    postal_code = forms.CharField(label="Code postal", max_length=20)
    city = forms.CharField(label="Ville", max_length=100)
    country = forms.ChoiceField(
        label="Pays", choices=[(code, COUNTRY_NAMES.get(code, code)) for code in SHIPPING_COUNTRIES], initial="FR"
    )
