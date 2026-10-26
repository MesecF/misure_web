# Renames brand to category. Written by hand so the table and columns are renamed
# and existing data is kept; constraints that refer to the old names are recreated
# in the following migration.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('catalog', '0004_article_variant_unique_per_tenant'),
    ]

    operations = [
        migrations.RemoveConstraint(model_name='brand', name='brand_code_unique_per_tenant'),
        migrations.RemoveConstraint(model_name='element', name='element_code_unique_per_brand'),
        migrations.RemoveConstraint(model_name='element', name='element_sort_order_unique_per_brand'),
        migrations.RenameModel(old_name='Brand', new_name='Category'),
        migrations.AlterModelTable(name='category', table='category'),
        migrations.RenameField(model_name='article', old_name='brand', new_name='category'),
        migrations.RenameField(model_name='element', old_name='brand', new_name='category'),
    ]
