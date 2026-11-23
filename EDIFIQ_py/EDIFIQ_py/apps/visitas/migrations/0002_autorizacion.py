from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
class Migration(migrations.Migration):
 dependencies=[('visitas','0001_initial'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
 operations=[migrations.AlterField(model_name='visita',name='estado',field=models.CharField(choices=[(x,x) for x in ['Pendiente','Autorizada','Rechazada','Ingresó','Finalizada','Cancelada']],default='Pendiente',max_length=20)),migrations.AddField(model_name='visita',name='autorizada_en',field=models.DateTimeField(blank=True,null=True)),migrations.AddField(model_name='visita',name='autorizada_por',field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='visitas_autorizadas',to=settings.AUTH_USER_MODEL))]
