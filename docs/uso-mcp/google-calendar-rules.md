# Google Calendar recurrence playbook

## Regla principal

Cuando uses `calendar_create_event` para un evento que se repite en el tiempo, crea un solo evento y representa la repeticion con `event.recurrence` usando RRULE de Google Calendar.

Nunca crees multiples eventos para simular recurrencia.

## Deteccion de recurrencia

Detecta recurrencia en frases como:
- todos los dias
- cada dia
- diario
- cada semana
- semanal
- cada mes
- mensual
- cada ano
- anual
- lunes a viernes
- cada lunes
- cada martes y jueves
- se repite
- repetir

## Mapeo base

- todos los dias -> `[`"`RRULE:FREQ=DAILY`"`]`
- cada semana -> `[`"`RRULE:FREQ=WEEKLY`"`]`
- cada mes -> `[`"`RRULE:FREQ=MONTHLY`"`]`
- cada ano -> `[`"`RRULE:FREQ=YEARLY`"`]`
- lunes a viernes -> `[`"`RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR`"`]`
- sabados y domingos -> `[`"`RRULE:FREQ=WEEKLY;BYDAY=SA,SU`"`]`
- cada lunes -> `[`"`RRULE:FREQ=WEEKLY;BYDAY=MO`"`]`
- cada martes y jueves -> `[`"`RRULE:FREQ=WEEKLY;BYDAY=TU,TH`"`]`

## Intervalos

- cada 2 dias -> `[`"`RRULE:FREQ=DAILY;INTERVAL=2`"`]`
- cada 2 semanas -> `[`"`RRULE:FREQ=WEEKLY;INTERVAL=2`"`]`
- cada 3 meses -> `[`"`RRULE:FREQ=MONTHLY;INTERVAL=3`"`]`

## Limites

- hasta una fecha -> agregar `UNTIL`
- por N veces -> agregar `COUNT=N`

## Reglas de decision

- si el usuario especifica dias concretos, usar `BYDAY`
- si el usuario especifica frecuencia numerica, usar `INTERVAL`
- si especifica fecha de fin, usar `UNTIL`
- si especifica cantidad de ocurrencias, usar `COUNT`
- si la recurrencia es ambigua, hacer una sola pregunta breve
- si no hay recurrencia, crear evento simple sin `recurrence`

## Reglas de formato

- usar JSON valido
- usar comillas normales `"`
- usar `dateTime` en RFC3339
- incluir `timeZone` cuando sea conocido

## Prompt recomendado

```text
Para herramientas de Google Calendar:

Si el usuario pide crear un evento recurrente, usa `calendar_create_event` con un solo evento y el campo `event.recurrence` en formato RRULE de Google Calendar.

Nunca generes multiples eventos separados para representar una recurrencia.

Interpreta estas expresiones:
- "todos los dias", "cada dia", "diario" -> `RRULE:FREQ=DAILY`
- "cada semana", "semanal" -> `RRULE:FREQ=WEEKLY`
- "cada mes", "mensual" -> `RRULE:FREQ=MONTHLY`
- "lunes a viernes" -> `RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR`
- "cada lunes" -> `RRULE:FREQ=WEEKLY;BYDAY=MO`

Si el usuario dice "hasta <fecha>", agrega `UNTIL`.
Si el usuario dice "<n> veces", agrega `COUNT=<n>`.

Ejemplos:
Usuario: "Crea un evento para practicar trading todos los dias a las 7:30"
Tool input:
{
  "calendar_id": "primary",
  "event": {
    "summary": "[TRADING] Practica y journal",
    "start": {"dateTime": "2026-03-17T07:30:00-03:00", "timeZone": "America/Santiago"},
    "end": {"dateTime": "2026-03-17T08:15:00-03:00", "timeZone": "America/Santiago"},
    "recurrence": ["RRULE:FREQ=DAILY"]
  }
}

Usuario: "Crea un evento de lunes a viernes a las 7:30"
Tool input:
{
  "calendar_id": "primary",
  "event": {
    "summary": "[TRADING] Practica y journal",
    "start": {"dateTime": "2026-03-17T07:30:00-03:00", "timeZone": "America/Santiago"},
    "end": {"dateTime": "2026-03-17T08:15:00-03:00", "timeZone": "America/Santiago"},
    "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"]
  }
}
```
