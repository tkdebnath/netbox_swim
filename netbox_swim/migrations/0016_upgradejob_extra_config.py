from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_swim', '0015_upgradejob_scheduled_time'),
    ]

    operations = [
        migrations.AddField(
            model_name='upgradejob',
            name='extra_config',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
