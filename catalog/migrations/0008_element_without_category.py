# Second step of 0007: element no longer belongs to a category. A separate migration
# because PostgreSQL cannot change the table in the same transaction as its data.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0007_general_elements'),
    ]

    operations = [
        migrations.RemoveConstraint(model_name='element', name='element_code_unique_per_category'),
        migrations.RemoveConstraint(model_name='element', name='element_sort_order_unique_per_category'),
        migrations.RemoveField(model_name='element', name='category'),
        migrations.RemoveField(model_name='element', name='sort_order'),
        migrations.AlterModelOptions(
            name='element',
            options={'ordering': ['code'], 'verbose_name': 'element', 'verbose_name_plural': 'elements'},
        ),
        migrations.AddConstraint(
            model_name='element',
            constraint=models.UniqueConstraint(fields=('tenant', 'code'), name='element_code_unique_per_tenant'),
        ),
    ]
