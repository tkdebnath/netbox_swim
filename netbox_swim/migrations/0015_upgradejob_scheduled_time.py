from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_swim', '0014_compliancesnapshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='upgradejob',
            name='scheduled_time',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='If set, the job will not execute until this date/time. Leave blank for immediate execution.',
            ),
        ),
    ]
