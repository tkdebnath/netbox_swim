from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_swim', '0013_validationcheck'),
    ]

    operations = [
        migrations.CreateModel(
            name='ComplianceSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(unique=True)),
                ('total_devices', models.IntegerField(default=0)),
                ('compliant', models.IntegerField(default=0)),
                ('non_compliant', models.IntegerField(default=0)),
                ('ahead', models.IntegerField(default=0)),
                ('unknown', models.IntegerField(default=0)),
            ],
            options={
                'ordering': ['date'],
            },
        ),
    ]
