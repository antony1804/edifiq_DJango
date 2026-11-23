from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='Persona',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('tipo_documento', models.CharField(max_length=20)),
                        ('numero_documento', models.CharField(max_length=20)),
                        ('nombres', models.CharField(max_length=100)),
                        ('apellidos', models.CharField(max_length=100)),
                        ('telefono', models.CharField(blank=True, max_length=30)),
                        ('correo', models.EmailField(blank=True, max_length=254)),
                        ('activo', models.BooleanField(default=True)),
                    ],
                ),
            ],
        ),
    ]
