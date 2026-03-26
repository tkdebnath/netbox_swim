from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Silences Django's 'unapplied changes' warning for WorkflowStep.action_type.
    The choices list is identical to 0017 — this migration records the current
    state so Django's migration checker stops flagging it as diverged.
    No actual database schema changes are made.
    """

    dependencies = [
        ('netbox_swim', '0017_alter_workflowstep_action_type'),
    ]

    operations = [
        # Re-record the exact choices list so Django's state matches models.py.
        # This is a no-op at the database level.
        migrations.AlterField(
            model_name='workflowstep',
            name='action_type',
            field=models.CharField(
                choices=[
                    ('readiness',     'Readiness Evaluation'),
                    ('precheck',      'Pre-Upgrade Validation'),
                    ('distribution',  'Distribute Image'),
                    ('activation',    'Activate / Reboot'),
                    ('wait',          'Wait Timer'),
                    ('ping',          'Ping Reachability'),
                    ('postcheck',     'Post-Upgrade Validation'),
                    ('verification',  'Verify Software Version'),
                    ('report',        'Generate Report'),
                ],
                max_length=20,
            ),
        ),
    ]
