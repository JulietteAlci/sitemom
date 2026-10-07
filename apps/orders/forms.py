from django import forms

from .cart import MAX_QUANTITY


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
