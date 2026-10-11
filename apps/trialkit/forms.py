from django import forms

from .models import SampleRing, validate_selection_size


class SampleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return obj.ring.name


class TrialKitForm(forms.Form):
    samples = SampleChoiceField(
        queryset=SampleRing.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Vos alliances à essayer",
    )
    include_sizer = forms.BooleanField(
        label="Ajouter un baguier pour mesurer votre tour de doigt", required=False, initial=True
    )
    message = forms.CharField(
        label="Un mot pour l'atelier (facultatif)",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["samples"].queryset = (
            SampleRing.objects.filter(is_active=True, ring__is_active=True).select_related("ring").with_availability()
        )

    def clean_samples(self):
        samples = self.cleaned_data["samples"]
        validate_selection_size(len(samples))
        unavailable = [sample.ring.name for sample in samples if sample.available <= 0]
        if unavailable:
            raise forms.ValidationError(
                "Ces modèles viennent d'être réservés par d'autres clients : "
                + ", ".join(unavailable) + ". Merci d'en choisir d'autres."
            )
        return samples
