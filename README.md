# Auto Cuadre

Aplicación local para crear y capturar el cuadre diario en el formato `.xls` institucional.

## Primer uso

1. Abra `Cuadre Digital.bat` desde el proyecto o el acceso **Cuadre Digital** del Escritorio.
2. En el panel oscuro de **Auto Cuadre**, seleccione **Cuadre del día** para registrar los movimientos.
3. Pulse **Añadir recibo** por cada recibo de salida y luego pulse **Guardar cuadre del día**.

El botón **Imprimir cuadre actual** permite guardar lo que está en pantalla y abrir el archivo en Excel; allí puede elegir impresora, copias y orientación desde **Archivo > Imprimir**. También permite enviar el último archivo guardado a la impresora predeterminada.

La interfaz muestra automáticamente el **Balance del día** (`E45`) y la **Diferencia** (`E49`). El panel derecho informa si el cuadre está cuadrado, tiene sobrante o faltante, y conserva avisos de registros y modificaciones de recibos durante la sesión.

El inicio incluye tres tarjetas: **Cuadre del día**, **Estadísticas** (con períodos semanal, mensual y anual) y **Lanzar cuadre actual**. Los controles de configuración e impresión están en la barra inferior.

El programa no crea carpetas. Usa la carpeta ya existente `CUADRE [Año] / [MES]` y guarda allí el archivo como `CUADRE CAJA DD-MM-AAAA.xls`.

`Cuadre del dia.bat` crea (si aún no existe) y abre el archivo del día en la aplicación de Excel predeterminada.

## Ubicación configurada

La aplicación usa directamente el modelo `C:\Users\User\Desktop\CUADRES CAJA\CUADRE 2026\AGOSTO\CUADRE CAJA MODELO.xls` y guarda todos los cuadres en `C:\Users\User\Desktop\CUADRES CAJA`. La interfaz no muestra campos para editar rutas.

## Requisitos de la plantilla

La plantilla debe contener estas celdas de entrada: `A5` (fecha), `E11` (mensualidades), `E14` (varios), `B24:D39` (recibos), `D41` (transferencias) y `E47` (efectivo). El programa solo lee `E45` (balance) y `E49` (diferencia), que son cálculos automáticos de Excel. Las fórmulas y el formato `.xls` permanecen intactos; el programa usa Microsoft Excel para registrar los datos.

Los recibos se insertan exclusivamente entre las filas 24 y 39, para proteger los cálculos que comienzan más abajo. La aplicación avisa antes de guardar si no hay espacio suficiente.
