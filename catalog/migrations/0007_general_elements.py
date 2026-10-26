# Elements become a general list per tenant; which elements a category measures (and in
# which order) moves to the new category_element table.
#
# Existing elements are moved: every element becomes a category_element row with its old
# category and sort order. Elements with the same code in several categories are merged
# into one; the one used in most measurements is kept (on a tie the oldest), and
# measurement values of the others are moved to it.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Count


def move_elements_to_categories(apps, schema_editor):
    Element = apps.get_model('catalog', 'Element')
    CategoryElement = apps.get_model('catalog', 'CategoryElement')
    MeasurementValue = apps.get_model('measurements', 'MeasurementValue')

    kept = {}
    for element in Element.objects.annotate(used=Count('values')).order_by('-used', 'id'):
        keep = kept.setdefault((element.tenant_id, element.code), element)
        CategoryElement.objects.create(
            tenant_id=element.tenant_id,
            category_id=element.category_id,
            element=keep,
            sort_order=element.sort_order,
            created_by_id=element.created_by_id,
        )
        if keep.pk != element.pk:
            MeasurementValue.objects.filter(element=element).update(element=keep)
            element.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('catalog', '0006_category_options_and_constraints'),
        ('measurements', '0003_category_options_and_constraints'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. New table for the category's elements
        migrations.CreateModel(
            name='CategoryElement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(blank=True, null=True, verbose_name='updated at')),
                ('sort_order', models.PositiveIntegerField(verbose_name='sort order')),
            ],
            options={
                'verbose_name': 'category element',
                'verbose_name_plural': 'category elements',
                'db_table': 'category_element',
                'ordering': ['category__code', 'sort_order'],
            },
        ),
        migrations.AddField(
            model_name='categoryelement',
            name='category',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='category_elements', to='catalog.category', verbose_name='category'),
        ),
        migrations.AddField(
            model_name='categoryelement',
            name='created_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='created by'),
        ),
        migrations.AddField(
            model_name='categoryelement',
            name='element',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='category_elements', to='catalog.element', verbose_name='element'),
        ),
        migrations.AddField(
            model_name='categoryelement',
            name='tenant',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='category_elements', to='accounts.tenant', verbose_name='tenant'),
        ),
        migrations.AddField(
            model_name='categoryelement',
            name='updated_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='updated by'),
        ),
        migrations.AddConstraint(
            model_name='categoryelement',
            constraint=models.UniqueConstraint(fields=('category', 'element'), name='category_element_unique'),
        ),
        migrations.AddConstraint(
            model_name='categoryelement',
            constraint=models.UniqueConstraint(fields=('category', 'sort_order'), name='category_element_sort_order_unique'),
        ),

        # 2. Move existing data
        migrations.RunPython(move_elements_to_categories, migrations.RunPython.noop),
    ]
