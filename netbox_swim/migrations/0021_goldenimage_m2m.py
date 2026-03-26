from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_swim', '0020_auto_20260326_swim'),
        ('dcim', '0001_initial'),
    ]

    operations = [
        # 1. Remove old UniqueConstraints
        migrations.RemoveConstraint(
            model_name='goldenimage',
            name='unique_golden_device_type',
        ),
        migrations.RemoveConstraint(
            model_name='goldenimage',
            name='unique_golden_hw_group',
        ),
        # 2. Remove old FK columns
        migrations.RemoveField(
            model_name='goldenimage',
            name='device_type',
        ),
        migrations.RemoveField(
            model_name='goldenimage',
            name='hardware_group',
        ),
        # 3. Add new M2M fields
        migrations.AddField(
            model_name='goldenimage',
            name='device_types',
            field=models.ManyToManyField(blank=True, related_name='golden_images', to='dcim.devicetype'),
        ),
        migrations.AddField(
            model_name='goldenimage',
            name='hardware_groups',
            field=models.ManyToManyField(blank=True, related_name='golden_images', to='netbox_swim.hardwaregroup'),
        ),
        # 4. Update ordering
        migrations.AlterModelOptions(
            name='goldenimage',
            options={'ordering': ['deployment_mode']},
        ),
    ]
