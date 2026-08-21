from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('core', '0010_application_created_at_application_updated_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='benefits',
            field=models.TextField(blank=True, help_text='Benefits provided by the service.'),
        ),
        migrations.AddField(
            model_name='service',
            name='requirements',
            field=models.TextField(blank=True, help_text='Documents or criteria required for the service.'),
        ),
        migrations.CreateModel(
            name='ElectedPosition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField()),
                ('term_length', models.PositiveIntegerField(help_text='Term length in years')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='VotingSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('start_date', models.DateTimeField()),
                ('end_date', models.DateTimeField()),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('active', 'Active'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_voting_sessions', to='auth.user')),
                ('position', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.electedposition')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Candidate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bio', models.TextField()),
                ('experience', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('approved', models.BooleanField(default=False)),
                ('rejection_reason', models.TextField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.user')),
                ('voting_session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.votingsession')),
            ],
            options={
                'unique_together': {('user', 'voting_session')},
            },
        ),
        migrations.CreateModel(
            name='Vote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('voted_at', models.DateTimeField(auto_now_add=True)),
                ('candidate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.candidate')),
                ('voter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.user')),
                ('voting_session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.votingsession')),
            ],
            options={
                'unique_together': {('voter', 'voting_session')},
            },
        ),
        migrations.CreateModel(
            name='ElectedMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('status', models.CharField(choices=[('active', 'Active'), ('completed', 'Completed'), ('resigned', 'Resigned'), ('terminated', 'Terminated')], default='active', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('position', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.electedposition')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.user')),
                ('voting_session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.votingsession')),
            ],
        ),
    ]