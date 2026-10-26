# Renames the brand snapshot columns to category; written by hand to keep existing data.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0005_rename_brand_to_category'),
        ('measurements', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(model_name='measurement', old_name='brand_code', new_name='category_code'),
        migrations.RenameField(model_name='measurement', old_name='brand_name', new_name='category_name'),
    ]
