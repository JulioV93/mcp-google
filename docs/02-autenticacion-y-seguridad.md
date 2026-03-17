# Autenticacion y seguridad

## Modelo de autenticacion

El servidor tiene dos planos de autenticacion distintos:

- `cliente o agente -> MCP server`
- `usuario final -> Google`

Ambos deben mantenerse separados para que el servidor pueda identificar de forma segura al usuario y operar sus herramientas Google sin mezclar credenciales.

## Autenticacion del cliente MCP

### Enfoque

- El cliente se autentica con `Bearer JWT`.
- El servidor valida firma, `iss`, `aud` y expiracion.
- La identidad del usuario se toma del claim `sub`.

### Claims minimos esperados

- `sub`
- `iss`
- `aud`
- `exp`

### Claims opcionales utiles

- `tenant_id`
- `email`
- `roles`
- `trace_id`
- `approved_tools`

### Regla de seguridad principal

Nunca se debe aceptar `user_id`, `external_subject` o `google_email` desde los argumentos de una tool como selector de identidad. La identidad siempre se resuelve desde el JWT autenticado.

### Aprobaciones explicitas para tools sensibles

- El servidor puede exigir aprobacion explicita para tools de alto riesgo.
- Cuando `REQUIRE_EXPLICIT_APPROVAL=true`, ciertas tools solo se ejecutan si el JWT del cliente incluye el claim `approved_tools` con el nombre exacto de la tool.
- Esto permite que la plataforma de agentes controle aprobaciones sin exponer decisiones al LLM.

## OAuth Google por usuario

### Flujo recomendado

- Authorization Code Flow.
- PKCE.
- `state` obligatorio.
- Redirect URI publica y fija.
- validacion de ID token devuelto por Google
- validacion de `email_verified`

### Flujo operativo

1. El cliente llama `auth_google_begin`.
2. El servidor identifica al usuario desde el JWT.
3. El servidor genera `state` y `code_verifier`.
4. El servidor devuelve la URL de consentimiento Google.
5. El usuario concede acceso.
6. Google redirige al callback del servidor.
7. El servidor valida `state` e intercambia `code` por tokens.
8. El servidor valida el ID token, incluyendo audiencia, clock skew y `email_verified`.
9. Los tokens se guardan cifrados y se vinculan al usuario.

## Scopes recomendados

- `openid`
- `https://www.googleapis.com/auth/userinfo.email`
- `https://www.googleapis.com/auth/userinfo.profile`
- `https://www.googleapis.com/auth/calendar`
- `https://www.googleapis.com/auth/tasks`
- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/gmail.compose`
- `https://www.googleapis.com/auth/gmail.modify`
- `https://www.googleapis.com/auth/drive`
- `https://www.googleapis.com/auth/documents`
- `https://www.googleapis.com/auth/spreadsheets`

No se recomienda usar `https://mail.google.com/` en v1 salvo necesidad real.

## Almacenamiento de tokens

### Reglas

- Access y refresh tokens cifrados en base de datos.
- La clave de cifrado vive fuera de la base de datos.
- Los tokens no se registran en logs.
- La desconexion debe borrar o invalidar la conexion del usuario.

### Persistencia esperada

- `access_token_encrypted`
- `refresh_token_encrypted`
- `expires_at`
- `granted_scopes`
- `google_subject`
- `google_email`

## Refresh automatico

- El servidor reconstruye credenciales Google desde la base de datos.
- Si el access token expiro, intenta refresh usando el refresh token.
- Si el refresh falla, la conexion pasa a estado de error o reconexion requerida.

## Controles de seguridad

### Entrada y validacion

- Validacion estricta con Pydantic.
- Fechas en RFC3339 para Calendar.
- Emails validos para Gmail.
- Limites razonables para textos y payloads.
- Gmail `messages.get` usa `metadataHeaders` cuando solo se necesitan headers minimos.

### Operaciones sensibles

Las siguientes operaciones deben auditarse con especial cuidado:

- `gmail_send_email`
- `gmail_delete_message`
- `calendar_delete_event`
- `tasks_delete_task`
- `tasks_delete_tasklist`

Estas operations pueden requerir aprobacion explicita cuando `REQUIRE_EXPLICIT_APPROVAL=true`.

En v1, `gmail_delete_message` se implementa como mover el mensaje a la papelera para evitar permisos mas amplios de borrado permanente.

### Seguridad HTTP y MCP remoto

- El servidor usa `Authorization: Bearer <token>` por header.
- Los tokens no deben ir en query string.
- Requests al endpoint MCP pueden validarse contra `Origin` permitido.
- El callback OAuth permanece publico, pero el resto de endpoints sensibles se protege con JWT.

### Observabilidad

- Logging estructurado.
- Redaccion de argumentos sensibles.
- Auditoria por usuario, tool y resultado.
- Rate limiting por sujeto autenticado.

### Redaccion minima obligatoria

- access token
- refresh token
- cuerpo completo de correos
- datos sensibles del usuario
- `subject`
- `body_text`
- `notes`
- `raw`

## Manejo de errores

Errores contractuales sugeridos:

- `unauthorized_client`
- `invalid_token`
- `google_connection_missing`
- `google_consent_required`
- `google_token_refresh_failed`
- `insufficient_scope`
- `resource_not_found`
- `rate_limited`
- `provider_error`
- `validation_error`
- `approval_required`
- `origin_not_allowed`

## Reintentos

Solo reintentar en errores transitorios del proveedor:

- `429`
- `500`
- `502`
- `503`
- `504`

No reintentar en:

- `400`
- `401`
- `403`
- `404`

## Riesgos principales

- mala propagacion de identidad desde el agente al servidor MCP
- refresh tokens revocados o mal configurados
- scopes excesivos desde el inicio
- fuga accidental de datos en logs
- errores de callback o redirect URI en Google OAuth
- origenes HTTP no confiables llamando al endpoint MCP remoto
- tools destructivas sin control de aprobacion en entornos remotos

## Variables de seguridad relevantes

- `ALLOWED_ORIGINS`
- `RATE_LIMIT_ENABLED`
- `RATE_LIMIT_RPM`
- `REQUIRE_EXPLICIT_APPROVAL`
- `APPROVAL_REQUIRED_TOOLS`
- `TOKEN_ENCRYPTION_KEY`
- `GOOGLE_ID_TOKEN_CLOCK_SKEW_SECONDS`
