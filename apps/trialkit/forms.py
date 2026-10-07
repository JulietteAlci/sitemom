from django import forms
from django.conf import settings

from apps.catalog.models import Ring

from .models import validate_selection_size


class RingChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return obj.name


class TrialKitForm(forms.Form):
    rings = RingChoiceField(
        queryset=Ring.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Vos alliances à essayer",
    )
    include_sizer = forms.BooleanField(label="Ajouter un baguier pour mesurer votre tour de doigt", required=False, initial=True)
    message = forms.CharField(
        label="Un mot pour l'atelier (facultatif)",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rings"].queryset = Ring.objects.filter(is_active=True, available_for_trial=True)
        self.fields["rings"].help_text = (
            f"Sélectionnez entre {settings.TRIAL_KIT_MIN} et {settings.TRIAL_KIT_MAX} modèles."
        )

    def clean_rings(self):
        rings = self.cleaned_data["rings"]
        validate_selection_size(len(rings))
        return rings
