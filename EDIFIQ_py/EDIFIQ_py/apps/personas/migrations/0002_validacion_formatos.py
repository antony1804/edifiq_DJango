from django.db import migrations, models
import django.core.validators
class Migration(migrations.Migration):
 dependencies=[('personas','0001_initial')]
 operations=[migrations.AlterField(model_name='persona',name='numero_documento',field=models.CharField(max_length=20,unique=True,validators=[django.core.validators.RegexValidator(r'^\d{1,10}$','El documento debe tener máximo 10 dígitos.')])),migrations.AlterField(model_name='persona',name='telefono',field=models.CharField(blank=True,max_length=30,validators=[django.core.validators.RegexValidator(r'^\d{1,10}$','El teléfono debe tener máximo 10 dígitos.')]))]
