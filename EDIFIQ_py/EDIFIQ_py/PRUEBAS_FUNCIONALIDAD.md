# EDIFIQ: pruebas de funcionalidad

1. En CMD configure `DB_PASSWORD` sin compartirla y ejecute `python manage.py check`.
2. Inicie el servidor: `python manage.py runserver`.
3. Cree una persona en Personas; abra Usuarios y selecciónela. Los campos de nombre, apellidos y correo se completan desde Personas.
4. Asigne rol Residente y apartamento. Debe crearse la relación en Residentes sin duplicar la persona.
5. Abra Apartamentos > ficha completa; compruebe residentes, visitas, paquetes, reservas y recibos del mismo apartamento.
6. En Personas, use el enlace Usuario y compruebe que el filtro muestra únicamente las cuentas asociadas.
7. En Usuarios, abra el enlace Persona y el enlace Apartamento.
8. En el reporte PDF de Apartamentos, filtre primero por torre y confirme que no aparezcan registros de otra torre.
9. Inicie sesión como Residente y compruebe que no puede consultar apartamentos ajenos ni administrar usuarios.
10. Intente crear una reserva con fin anterior al inicio y otra superpuesta: ambas deben mostrar error.

No ejecute `makemigrations` si no cambió modelos: esta actualización no modifica el esquema.
