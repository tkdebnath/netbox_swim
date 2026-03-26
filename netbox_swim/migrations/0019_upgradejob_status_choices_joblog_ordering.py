from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Syncs Django migration state to match current models.py:
    1. UpgradeJob.status — records the choices= list (no DB schema change)
    2. JobLog.Meta.ordering — fixes '-timestamp' vs 'timestamp' (no DB schema change)
    Both are no-ops at the database level.
    """

    dependencies = [
        ('netbox_swim', '0018_workflowstep_choices_sync'),
    ]

    operations = [
        # 1. Record UpgradeJob.status choices so Django's state matches models.py
        migrations.AlterField(
            model_name='upgradejob',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending',   'Pending'),
                    ('scheduled', 'Scheduled'),
                    ('running',   'Running'),
                    ('completed', 'Completed'),
                    ('failed',    'Failed'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
        # 2. Fix JobLog ordering: models.py uses '-timestamp' (descending)
        migrations.AlterModelOptions(
            name='joblog',
            options={'ordering': ['-timestamp']},
        ),
    ]
