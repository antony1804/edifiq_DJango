from django.db import migrations, models
import django.db.models.deletion
class Migration(migrations.Migration):
 dependencies=[('residentes','0001_initial'),('personas','0001_initial')]
 operations=[migrations.CreateModel(name='Residente',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('tipo',models.CharField(choices=[('Propietario','Propietario'),('Arrendatario','Arrendatario'),('Familiar','Familiar')],default='Propietario',max_length=20)),('activo',models.BooleanField(default=True)),('apartamento',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='residentes.apartamento')),('persona',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='personas.persona'))],options={'constraints':[models.UniqueConstraint(fields=('persona','apartamento'),name='unico_residente_apartamento')]})]
