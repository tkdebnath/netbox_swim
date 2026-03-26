from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_swim', '0021_goldenimage_m2m'),
    ]

    operations = [
        migrations.AddField(
            model_name='fileserver',
            name='priority',
            field=models.PositiveIntegerField(
                default=100,
                help_text='Lower number = higher preference. Used to order candidates when multiple file servers match.',
            ),
        ),
        migrations.AddField(
            model_name='fileserver',
            name='is_global_default',
            field=models.BooleanField(
                default=False,
                help_text='If true, this server is used as a last-resort fallback when no regional match is found.',
            ),
        ),
        migrations.AlterModelOptions(
            name='fileserver',
            options={'ordering': ['priority', 'name']},
        ),
    ]
