import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('netbox_swim', '0011_devicesyncrecord_live_facts_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='joblog',
            name='message',
        ),
        migrations.RemoveField(
            model_name='joblog',
            name='result',
        ),
        migrations.AddField(
            model_name='joblog',
            name='is_success',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='joblog',
            name='log_output',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='joblog',
            name='step',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
