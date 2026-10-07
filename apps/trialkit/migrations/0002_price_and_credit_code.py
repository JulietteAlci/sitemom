import secrets

from django.db import migrations, models

CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def assign_codes(apps, schema_editor):
    TrialKitOrder = apps.get_model("trialkit", "TrialKitOrder")
    used = set()
    for kit in TrialKitOrder.objects.filter(credit_code__isnull=True):
        while True:
            raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
            code = f"ESSAI-{raw[:4]}-{raw[4:]}"
            if code not in used:
                break
        used.add(code)
        kit.credit_code = code
        kit.save(update_fields=["credit_code"])


class Migration(migrations.Migration):
    dependencies = [
        ("trialkit", "0001_initial"),
    ]

    operations = [
        migrations.RenameField("trialkitorder", "deposit", "price"),
        migrations.AlterField(
            model_name="trialkitorder",
            name="price",
            field=models.DecimalField(decimal_places=2, max_digits=8, verbose_name="prix du coffret (€)"),
        ),
        migrations.AddField(
            model_name="trialkitorder",
            name="credit_code",
            field=models.CharField(editable=False, max_length=20, null=True),
        ),
        migrations.RunPython(assign_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="trialkitorder",
            name="credit_code",
            field=models.CharField(
                editable=False,
                help_text="À saisir dans le panier pour déduire le prix du coffret de la commande d'alliances.",
                max_length=20,
                unique=True,
                verbose_name="code de déduction",
            ),
        ),
        migrations.AlterField(
            model_name="trialkitorder",
            name="fulfillment",
            field=models.CharField(
                choices=[
                    ("to_prepare", "À préparer"),
                    ("shipped", "Expédié"),
                    ("returned", "Retourné"),
                    ("converted", "Converti en commande"),
                ],
                default="to_prepare",
                max_length=12,
                verbose_name="logistique",
            ),
        ),
    ]
