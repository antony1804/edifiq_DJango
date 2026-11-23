from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('usuarios','0001_initial'),('personas','0001_initial')]
    operations = [migrations.AddField(model_name='perfil',name='persona',field=models.OneToOneField(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,db_constraint=False,related_name='perfil_usuario',to='personas.persona'))]
