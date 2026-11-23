from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='Torre',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('nombre_torre', models.CharField(max_length=20)),
                    ],
                ),
                migrations.CreateModel(
                    name='Apartamento',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('numero_apartamento', models.CharField(max_length=10)),
                        ('piso', models.IntegerField()),
                        ('activo', models.BooleanField(default=True)),
                        ('torre', models.ForeignKey(on_delete=models.deletion.PROTECT, to='residentes.torre')),
                    ],
                ),
            ],
        ),
    ]
