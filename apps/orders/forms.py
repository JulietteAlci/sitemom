from django import forms
from django.core.validators import MaxLengthValidator

from .cart import MAX_QUANTITY
from .payments import SHIPPING_COUNTRIES


COMMENT_MAX_LENGTH = 200


class AddToCartForm(forms.Form):
    """Product page form. Metal, stone and size come from the option panel (hidden fields)."""

    size = forms.TypedChoiceField(label="Taille", coerce=int, widget=forms.HiddenInput)
    metal = forms.ChoiceField(label="Métal", required=False, widget=forms.HiddenInput)
    stone = forms.TypedChoiceField(label="Pierre", coerce=int, required=False, widget=forms.HiddenInput)
    engraving = forms.CharField(label="Votre gravure", required=False)
    comment = forms.CharField(
        label="Commentaire",
        max_length=COMMENT_MAX_LENGTH,
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 3, "maxlength": COMMENT_MAX_LENGTH,
                   "placeholder": "Date de livraison souhaitée, demande particulière…"}
        ),
    )
    quantity = forms.TypedChoiceField(
        label="Quantité", coerce=int, choices=[(i, i) for i in range(1, MAX_QUANTITY + 1)], required=False,
        empty_value=1, widget=forms.HiddenInput, initial=1,
    )

    def __init__(self, *args, ring, **kwargs):
        super().__init__(*args, **kwargs)
        self.ring = ring
        self.fields["size"].choices = [(s, s) for s in ring.sizes]
        self.fields["metal"].choices = [(m.code, m.name) for m in ring.available_metals()]
        stone_ids = [(o.pk, o.pk) for o in ring.stone_options.all()]
        self.fields["stone"].choices = stone_ids
        self.fields["stone"].required = bool(stone_ids)
        if ring.engravable:
            self.fields["engraving"].max_length = ring.engraving_max_length
            self.fields["engraving"].widget.attrs.update(
                {"maxlength": ring.engraving_max_length, "placeholder": "Ex. : J & M — 12.06.2027"}
            )
            self.fields["engraving"].validators.append(MaxLengthValidator(ring.engraving_max_length))
        else:
            del self.fields["engraving"]

    def clean_engraving(self):
        return self.cleaned_data.get("engraving", "").strip()

    def clean_metal(self):
        default = self.ring.default_metal()
        return self.cleaned_data.get("metal") or (default.code if default else "")

    def clean_comment(self):
        return self.cleaned_data.get("comment", "").strip()


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
