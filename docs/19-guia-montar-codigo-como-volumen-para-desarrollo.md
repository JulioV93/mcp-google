# Guia para montar el codigo como volumen para desarrollo

> Guía de desarrollo. Para el Home Lab de producción sigue [deploy/README.md](../deploy/README.md): imagen por digest, SQLite persistente y túnel existente. Construye fuera del Acer.

## Objetivo

Esta guia explica que significa montar el codigo fuente del proyecto como volumen dentro de un contenedor Docker, para que sirve, cuando conviene usarlo y como hacerlo con este servidor MCP. El objetivo es que entiendas el concepto y puedas usarlo como herramienta de desarrollo sin confundirlo con un despliegue de produccion.

## Idea principal

Montar el codigo como volumen significa conectar una carpeta real de tu maquina o servidor host con una carpeta dentro del contenedor.

En la practica, Docker hace que una ruta del host aparezca dentro del contenedor. De esa forma, el contenedor no usa solamente el codigo copiado en la imagen, sino que ve directamente los archivos vivos del disco del host.

## Definicion sencilla

Piensa en esto como una "ventana compartida" entre tu maquina y el contenedor:

- tu editas archivos en el host
- el contenedor ve esos mismos archivos casi inmediatamente
- la app dentro del contenedor puede arrancar usando ese codigo actualizado

## Por que esto es util en desarrollo

Sin volumen, el flujo normal es este:

1. cambias un archivo
2. reconstruyes la imagen con `docker build`
3. recreas el contenedor
4. recien entonces ves el cambio ejecutandose

Con volumen, en muchos casos el flujo mejora:

1. cambias un archivo
2. el contenedor ya ve el archivo cambiado
3. si el servidor tiene autorecarga, reinicia automaticamente
4. ves el cambio mucho mas rapido

En este proyecto, `app/main.py` activa `reload` cuando `APP_ENV=development`, por lo que este enfoque encaja bien para desarrollo local o remoto controlado.

## Definiciones clave

### Host

La maquina real donde ejecutas Docker. Puede ser tu laptop, tu PC o un servidor.

### Contenedor

Proceso aislado que ejecuta la aplicacion.

### Volumen o bind mount

Union entre una carpeta del host y una carpeta del contenedor.

### Imagen

Paquete base con dependencias y codigo preparado. Cuando usas un volumen de codigo, parte del contenido incluido en la imagen puede quedar "tapado" visualmente por los archivos montados desde el host.

### Autorecarga

Mecanismo por el cual el servidor detecta cambios en archivos y se reinicia automaticamente. En este proyecto depende de `APP_ENV=development`.

## Cuando conviene usar esta opcion

Usa este enfoque cuando quieras:

- desarrollar mas rapido sin reconstruir la imagen en cada cambio
- editar codigo desde el host con tu editor habitual
- probar cambios pequeños continuamente
- trabajar con Docker sin perder la comodidad de editar archivos normales

## Cuando no conviene usar esta opcion

No es la opcion ideal para:

- produccion
- entornos donde necesitas una version totalmente congelada e inmutable
- despliegues donde no quieres depender del estado del disco del host
- escenarios donde varias personas modifican archivos directamente en el mismo servidor

## Como funciona tecnicamente

Supongamos que el contenedor espera el codigo en `/app` y tu proyecto esta en tu host en `/ruta/al/proyecto`.

Si ejecutas un contenedor con un montaje como este:

```bash
-v /ruta/al/proyecto:/app
```

Docker hace que la carpeta `/app` dentro del contenedor muestre el contenido real de `/ruta/al/proyecto` del host.

Eso significa que, aunque la imagen ya traia una copia del codigo dentro de `/app`, durante la ejecucion veras principalmente los archivos del host montados sobre esa ruta.

## Requisitos previos para este proyecto

- tener el codigo fuente disponible en el host
- Docker instalado
- un archivo `.env` valido
- idealmente una imagen base ya construida para no reinstalar dependencias en cada arranque

## Opcion 1: usar `docker run` con el codigo montado

Desde la raiz del proyecto:

```bash
docker build -t mcp-google:dev .
```

Despues arranca el contenedor montando el proyecto:

```bash
docker run --rm \
  -p 127.0.0.1:8000:8000 \
  --env-file .env \
  -e APP_ENV=development \
  -v "$(pwd)":/app \
  -v mcp_google_data:/app/data \
  mcp-google:dev
```

### Que hace este comando

- publica el puerto `8000`
- carga variables desde `.env`
- fuerza `APP_ENV=development`
- monta la carpeta actual del proyecto dentro de `/app`
- crea un volumen separado para `/app/data`

## Por que conviene mantener `/app/data` en un volumen separado

Este proyecto puede usar SQLite con una ruta como `sqlite:///./data/dev.db`.

Si montas todo el proyecto sobre `/app`, el directorio `data` podria quedar mezclado con los archivos del repositorio o comportarse de forma menos ordenada segun tu flujo de trabajo.

Separar `/app/data` ayuda a:

- persistir datos de prueba
- no ensuciar el repositorio con bases SQLite temporales
- recrear el contenedor sin perder el archivo de base de datos

## Opcion 2: usar Docker Compose para desarrollo con volumen

Puedes crear un archivo `docker-compose.dev.yml` como este:

```yaml
services:
  postgres:
    image: postgres:16
    container_name: mcp-google-postgres-dev
    environment:
      POSTGRES_DB: mcp_google
      POSTGRES_USER: mcp_google
      POSTGRES_PASSWORD: mcp_google
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  mcp-google:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: mcp-google-app-dev
    depends_on:
      - postgres
    env_file:
      - .env
    environment:
      APP_ENV: development
      DATABASE_URL: postgresql+psycopg://mcp_google:mcp_google@postgres:5432/mcp_google
      APP_HOST: 0.0.0.0
      APP_PORT: 8000
    ports:
      - "8000:8000"
    volumes:
      - .:/app
      - mcp_google_data:/app/data
    command: ["python", "-m", "app.main"]

volumes:
  postgres_data:
  mcp_google_data:
```

Arranque:

```bash
docker compose -f docker-compose.dev.yml up --build
```

## Que ventajas ofrece este flujo

- cambios mas rapidos durante desarrollo
- no necesitas reconstruir la imagen por cada ajuste pequeno
- puedes usar tu editor favorito sobre archivos normales del host
- la app puede recargarse automaticamente si detecta cambios

## Que desventajas o riesgos tiene

- el comportamiento depende del estado real de tu carpeta local
- puedes introducir diferencias entre lo que pruebas y la imagen final de produccion
- si borras o rompes archivos del host, el contenedor tambien lo sufrira
- no es una practica recomendada como despliegue final en produccion

## Diferencia entre este enfoque y reconstruir la imagen cada vez

### Con reconstruccion continua

- mas lento
- mas fiel a la imagen final
- mejor para validar exactamente lo que vas a publicar

### Con volumen montado

- mas rapido para iterar
- mejor para desarrollo diario
- menos representativo de una imagen completamente cerrada

## Buenas practicas

- usa este enfoque solo en desarrollo
- manten `APP_ENV=development`
- usa una rama Git para tus cambios
- si el cambio ya esta listo, reconstruye la imagen final y validala sin volumen
- no confundas el contenedor de desarrollo con el despliegue definitivo

## Errores frecuentes

### Cambio un archivo y no veo el resultado

Puede deberse a que:

- el servidor no reinicio automaticamente
- `APP_ENV` no esta en `development`
- cambiaste un archivo no observado por el mecanismo de recarga

### El contenedor funciona raro despues de montar el volumen

Puede deberse a que el codigo del host esta "tapando" lo que venia dentro de la imagen, y existe alguna diferencia entre ambos estados.

### La app pierde datos de SQLite

Puede deberse a que no mantuviste `/app/data` en un volumen persistente separado.

## Resumen practico

Montar el codigo como volumen significa que el contenedor usa directamente los archivos del proyecto que estan en tu maquina o servidor host.

Este enfoque sirve para desarrollar mas rapido, porque te permite editar archivos y probar cambios sin reconstruir la imagen en cada iteracion.

Para este proyecto, es una buena herramienta de desarrollo, pero no debe sustituir el flujo final de construir una imagen limpia y ejecutar esa version cerrada cuando quieras un despliegue mas estable.
