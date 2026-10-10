# Auto Cuadre

Aplicación local para crear y capturar el cuadre diario en el formato `.xls` institucional.

## Instalación

1. Instale Python 3 y Microsoft Excel.
2. Instale el lector rápido de `.xls` (recomendado, hace las estadísticas casi instantáneas):
   `python -m pip install -r requirements.txt`
3. Copie `config.example.json` como `config.json` (o configure todo desde **Configuración**).

## Uso

Abra `Cuadre Digital.bat`. Se muestra una pantalla de carga que, en segundo plano:

1. Busca e instala actualizaciones (si hay un origen configurado) y se reinicia sola.
2. Revisa el mes en curso y avisa de los **días laborables sin cuadre**.
3. Abre la ventana principal.

Toda la navegación ocurre en **una sola ventana**: **Inicio**, **Cuadre del día**, **Estadísticas** y **Configuración**.

### Cuadre del día
Registre mensualidades, ingresos varios, transferencias y efectivo; añada los recibos de salida y pulse **Guardar cuadre del día**. El panel se adapta a pantallas pequeñas (con desplazamiento) y el guardado se hace en segundo plano. Se muestran el **Balance** (`E45`) y la **Diferencia** (`E49`) y si el cuadre está cuadrado, con sobrante o faltante.

### Estadísticas
Períodos **Semanal / Mensual / Anual** o un **período personalizado de mes a mes (máximo 12 meses)**. Muestra una barra de progreso global, la tabla por mes (se llena a medida que cada mes termina) y el gráfico. Los resultados se guardan en caché (`stats_cache.json`), así que los meses cerrados no se vuelven a leer.

### Configuración
Rutas del modelo y de la carpeta principal, origen de actualizaciones, **días laborables**, feriados y si se avisa del cuadre de hoy. Por defecto no se labora el domingo.

El programa no crea carpetas: usa las existentes `CUADRE [Año] / [MES]` y guarda `CUADRE CAJA DD-MM-AAAA.xls`.

`Cuadre del dia.bat` crea (si no existe) y abre el archivo del día directamente en Excel.

## Actualizaciones automáticas

1. Cambie lo que necesite y ejecute: `python make_release.py 1.1.0 "Notas de la versión"`.
2. Publique `release/auto_cuadre_1.1.0.zip` y `release/version.json` en la misma carpeta compartida o sitio **HTTPS**.
3. En **Configuración > Origen de actualizaciones** ponga la ruta o URL de `version.json`.

Cada PC verifica el SHA-256 del paquete, respalda lo que reemplaza (`.update_backup`) y revierte si algo falla. Nunca se tocan `config.json` ni la caché. El repositorio privado de GitHub no sirve como origen sin incrustar credenciales en cada PC.

## Requisitos de la plantilla

La plantilla debe contener estas celdas de entrada: `A5` (fecha), `E11` (mensualidades), `E14` (varios), `B24:D39` (recibos), `D41` (transferencias) y `E47` (efectivo). El programa solo lee `E45` (balance) y `E49` (diferencia), que son cálculos automáticos de Excel. Las fórmulas y el formato `.xls` permanecen intactos.

Los recibos se insertan exclusivamente entre las filas 24 y 39. La aplicación avisa antes de guardar si no hay espacio suficiente.
