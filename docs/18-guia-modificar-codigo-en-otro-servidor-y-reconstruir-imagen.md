# Guia para modificar codigo en otro servidor y reconstruir la imagen

> Guía de desarrollo. Para el Home Lab de producción sigue [deploy/README.md](../deploy/README.md): imagen por digest, SQLite persistente y túnel existente. Construye fuera del Acer.

## Objetivo

Esta guia explica como trabajar con el codigo fuente del proyecto directamente en otro servidor o PC, realizar cambios, volver a construir la imagen Docker y ejecutar la version actualizada. A diferencia del flujo basado solo en `docker pull`, aqui si existe trabajo de desarrollo sobre el codigo.

## Cuando usar esta opcion

Usa esta opcion cuando necesites:

- editar archivos Python o configuraciones del proyecto en el otro equipo
- probar cambios sin depender de tu maquina principal
- reconstruir una imagen nueva desde el mismo servidor donde estas trabajando
- dejar el servidor preparado tambien como entorno de desarrollo o mantenimiento

## Que cambia respecto al despliegue solo con imagen

Cuando ejecutas solo una imagen descargada desde Docker Hub, el codigo ya viene empaquetado dentro de esa imagen y no se edita normalmente.

Cuando quieres modificar la aplicacion, necesitas acceder al codigo fuente real. Eso implica trabajar con el repositorio, cambiar archivos y generar una imagen nueva basada en esos cambios.

## Definiciones clave

### Codigo fuente

Conjunto de archivos editables del proyecto: Python, configuraciones, documentacion, migraciones y demas recursos versionados.

### Repositorio

Carpeta del proyecto gestionada por Git. Contiene historial, ramas y archivos necesarios para reconstruir la app.

### Reconstruir la imagen

Volver a ejecutar `docker build` para crear una nueva imagen que incluya tus ultimos cambios.

### Publicar una nueva version

Subir la nueva imagen a Docker Hub con un tag actualizado para que otros equipos la descarguen.

## Requisitos previos

- Docker instalado en el servidor o PC donde editaras el codigo
- Git instalado si vas a clonar el repositorio
- acceso al repositorio del proyecto
- permisos para editar archivos en esa maquina
- variables de entorno disponibles para ejecutar la app

## Opcion recomendada: clonar el repositorio en el otro servidor

Esta es la forma mas ordenada y mantenible.

### Paso 1: clonar el proyecto

Ejemplo:

```bash
git clone <URL_DEL_REPOSITORIO>
cd mcp-google
```

Si el proyecto ya existe en esa maquina, puedes actualizarlo con `git pull` en lugar de clonarlo otra vez.

### Paso 2: preparar variables de entorno

Crea un archivo `.env` basandote en:

- `.env.example`
- `docs/12-plantilla-env-pruebas-reales.md`

Revisa especialmente:

- `DATABASE_URL`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`
- `TOKEN_ENCRYPTION_KEY`

## Paso 3: editar el codigo

Ya con el repositorio presente en el servidor, puedes modificar archivos con el editor que prefieras, por ejemplo:

- `vim`
- `nano`
- `code` si usas VS Code remoto
- cualquier IDE conectado por SSH

Ejemplos de archivos frecuentes en este proyecto:

- `app/main.py`
- `app/asgi.py`
- `app/services/`
- `app/routes/`
- `migrations/`

## Paso 4: reconstruir la imagen con tus cambios

Desde la raiz del proyecto:

```bash
docker build -t mcp-google:local .
```

Si quieres un nombre listo para publicar:

```bash
docker build -t TU_USUARIO_DOCKERHUB/mcp-google:dev-servidor .
```

## Paso 5: ejecutar la imagen reconstruida

Ejemplo simple:

```bash
docker run --rm -p 127.0.0.1:8000:8000 --env-file .env mcp-google:local
```

Si usas `docker compose`:

```bash
docker compose up --build
```

En ese caso, Compose reconstruye y levanta los servicios definidos en `docker-compose.yml`.

## Paso 6: aplicar migraciones si hace falta

Si tus cambios afectan base de datos o si estas preparando el entorno por primera vez, aplica migraciones:

```bash
docker compose run --rm mcp-google alembic upgrade head
```

O con la imagen local:

```bash
docker run --rm --env-file .env mcp-google:local alembic upgrade head
```

## Paso 7: publicar tu nueva imagen si quieres reutilizarla en otros equipos

Una vez validada la nueva version:

```bash
docker login
docker push TU_USUARIO_DOCKERHUB/mcp-google:dev-servidor
```

Tambien puedes usar un tag mas formal, por ejemplo `v1.1` o `2026-05-18-fix-oauth`.

## Otras formas de llevar el codigo al servidor

### Copiar archivos manualmente

Tambien puedes enviar el proyecto por:

- `scp`
- `rsync`
- un archivo `.zip`
- una carpeta compartida

Esto funciona, pero tiene desventajas:

- es facil perder control de versiones
- cuesta mas saber que cambio se hizo y cuando
- es mas incomodo sincronizar con otros equipos

Por eso, si el proyecto ya usa Git, clonar el repositorio sigue siendo la mejor practica.

## Lo que no se recomienda

### Editar archivos directamente dentro de un contenedor ya arrancado

Aunque tecnicamente puedes entrar con:

```bash
docker exec -it mcp-google-app sh
```

y tocar archivos dentro del contenedor, esto no es una buena practica para desarrollo normal.

Problemas principales:

- los cambios pueden perderse cuando el contenedor se elimina o recrea
- no quedan versionados en Git automaticamente
- es mas dificil repetir el proceso en otra maquina
- el estado final del contenedor puede diferir del codigo real del repositorio

## Ventajas de trabajar con el repo en el otro servidor

- puedes editar, probar y reconstruir en el mismo entorno
- tienes control total sobre el codigo y las configuraciones
- puedes usar Git para mantener historial y ramas
- puedes generar nuevas imagenes listas para Docker Hub

## Desventajas de este enfoque

- requiere mas herramientas y mas cuidado que solo hacer `docker pull`
- puedes mezclar entorno de desarrollo con entorno de produccion si no separas bien el uso del servidor
- necesitas disciplina para gestionar ramas, secretos y versiones

## Flujo recomendado de trabajo

El flujo mas limpio suele ser este:

1. clonar el repositorio en el otro servidor
2. crear o ajustar el `.env`
3. editar el codigo
4. reconstruir la imagen
5. ejecutar pruebas basicas
6. levantar el contenedor actualizado
7. si quieres distribuirlo, subir la nueva imagen a Docker Hub

## Errores frecuentes

### Hice cambios en el codigo pero el contenedor sigue usando la version vieja

Suele indicar que olvidaste reconstruir la imagen o que sigues arrancando una etiqueta antigua.

### El servidor remoto tiene el codigo, pero Git muestra diferencias inesperadas

Suele indicar cambios locales sin commit, archivos generados o ramas distintas a las esperadas.

### La nueva imagen arranca, pero falla OAuth

Suele indicar que olvidaste ajustar `GOOGLE_REDIRECT_URI` al host real del otro servidor.

## Resumen practico

Si en el otro servidor quieres modificar el comportamiento de la aplicacion, si necesitas tener el codigo fuente alli.

La forma recomendada es:

1. clonar el repositorio
2. editar el codigo
3. reconstruir la imagen
4. ejecutar la nueva version
5. opcionalmente publicarla en Docker Hub

Este flujo convierte al otro servidor en una maquina capaz de desarrollar y generar nuevas versiones del proyecto.
