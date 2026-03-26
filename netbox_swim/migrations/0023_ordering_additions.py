from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_swim', '0022_fileserver_priority_fallback'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='checktemplate',
            options={'ordering': ['name']},
        ),
        migrations.AlterModelOptions(
            name='upgradejob',
            options={'ordering': ['-created']},
        ),
        migrations.AlterModelOptions(
            name='validationcheck',
            options={'ordering': ['name']},
        ),
        migrations.AlterModelOptions(
            name='workflowtemplate',
            options={'ordering': ['name']},
        ),
    ]
