import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('netbox_swim', '0012_joblog_update'),
    ]

    operations = [
        migrations.CreateModel(
            name='ValidationCheck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('category', models.CharField(default='genie', max_length=20)),
                ('command', models.CharField(max_length=255)),
                ('phase', models.CharField(default='both', max_length=10)),
            ],
            options={'ordering': ('name',)},
        ),
        migrations.CreateModel(
            name='CheckTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('checks', models.ManyToManyField(related_name='templates', to='netbox_swim.validationcheck')),
            ],
            options={'ordering': ('name',)},
        ),
    ]
