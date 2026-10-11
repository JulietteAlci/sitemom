from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0003_ring_sku"),
        ("trialkit", "0005_sample_rings"),  # dummies are created from this flag first
    ]

    operations = [
        migrations.RemoveField(model_name="ring", name="available_for_trial"),
    ]
