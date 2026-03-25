from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_swim', '0016_upgradejob_extra_config'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workflowstep',
            name='action_type',
            field=models.CharField(choices=[
                ('readiness', 'Readiness Evaluation'), 
                ('precheck', 'Pre-Upgrade Validation'), 
                ('distribution', 'Distribute Image'), 
                ('activation', 'Activate / Reboot'), 
                ('wait', 'Wait Timer'), 
                ('ping', 'Ping Reachability'), 
                ('postcheck', 'Post-Upgrade Validation'), 
                ('verification', 'Verify Software Version'), 
                ('report', 'Generate Report')
            ], max_length=20),
        ),
    ]
