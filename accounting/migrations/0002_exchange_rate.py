from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExchangeRate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("currency", models.CharField(max_length=3)),
                ("rate_date", models.DateField()),
                ("rate_type", models.CharField(choices=[("closing", "Closing"), ("average", "Average")], default="closing", max_length=10)),
                ("rate", models.DecimalField(decimal_places=8, max_digits=20)),
                ("source", models.CharField(blank=True, max_length=100)),
            ],
            options={
                "ordering": ["-rate_date"],
                "unique_together": {("currency", "rate_date", "rate_type")},
            },
        ),
    ]

