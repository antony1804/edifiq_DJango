from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('residentes', '0001_initial'),
        migrations.swappable_dependency('auth.user')
    ]

    operations = []
