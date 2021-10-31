# Generated by Django 3.2.8 on 2021-10-30 19:51

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Keyword',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('keyword', models.CharField(max_length=500, unique=True, verbose_name='Keyword')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]