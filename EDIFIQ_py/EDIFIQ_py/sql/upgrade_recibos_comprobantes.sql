-- Revisar antes de ejecutar en la base de datos de la aplicación.
-- Agrega el campo que guarda la ruta privada del comprobante sin sobrescribir datos.
SET @comprobante_column_exists = (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'recibo'
      AND column_name = 'comprobante'
);

SET @comprobante_ddl = IF(
    @comprobante_column_exists = 0,
    'ALTER TABLE recibo ADD COLUMN comprobante VARCHAR(255) NULL',
    'SELECT ''La columna recibo.comprobante ya existe'' AS resultado'
);
PREPARE comprobante_stmt FROM @comprobante_ddl;
EXECUTE comprobante_stmt;
DEALLOCATE PREPARE comprobante_stmt;

-- El estado es requerido para enviar comprobantes a revisión sin duplicar registros.
INSERT INTO estado_recibo (nombre)
SELECT 'Pendiente por revisar'
WHERE NOT EXISTS (
    SELECT 1
    FROM estado_recibo
    WHERE LOWER(nombre) = LOWER('Pendiente por revisar')
);
