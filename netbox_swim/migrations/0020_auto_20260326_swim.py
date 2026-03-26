# Generated manually

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('netbox_swim', '0019_upgradejob_status_choices_joblog_ordering'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='goldenimage',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='goldenimage',
            constraint=models.UniqueConstraint(condition=models.Q(('device_type__isnull', False)), fields=('device_type', 'deployment_mode'), name='unique_golden_device_type'),
        ),
        migrations.AddConstraint(
            model_name='goldenimage',
            constraint=models.UniqueConstraint(condition=models.Q(('hardware_group__isnull', False)), fields=('hardware_group', 'deployment_mode'), name='unique_golden_hw_group'),
        ),
        migrations.AlterField(
            model_name='softwareimage',
            name='file_size_bytes',
            field=models.BigIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='softwareimage',
            name='hash_md5',
            field=models.CharField(max_length=32),
        ),
        migrations.AlterField(
            model_name='softwareimage',
            name='hash_sha512',
            field=models.CharField(max_length=128),
        ),
    ]
