from django.db import migrations, models
class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_add_complaint_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='application',
            name='rejection_reason',
            field=models.TextField(blank=True, help_text='Required when application is rejected', null=True),
        ),
        migrations.AddField(
            model_name='application',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
