# Google Calendar event colors design

## Objective

Allow MCP clients to set or change the color of Google Calendar events when creating or updating them.

## Scope

This change applies only to Google Calendar events handled by the existing Calendar MCP tools:

- `calendar_create_event`
- `calendar_update_event`
- normalized event responses returned by Calendar service methods

Out of scope:

- Google Tasks color handling
- custom friendly color names such as `red` or `blue`
- local enforcement of a fixed allowed color list

## Recommended approach

Implement optional native support for Google Calendar `colorId` and pass it through end to end.

- accept `colorId` in the incoming event payload
- serialize it to Google Calendar unchanged during create and update
- expose the current color in normalized service responses as `color_id`

This approach fits the existing Calendar architecture because recurrence and reminders already follow the same pattern: schema validation, service serialization, provider passthrough, and normalized output.

## Architecture impact

### Schema layer

Add an optional `color_id` field with alias `colorId` to `CalendarEventInput` in `app/schemas/calendar.py`.

Effect:

- MCP clients can send `event.colorId` in create and update calls
- requests without a color remain valid and unchanged

### Service layer

Keep the current `model_dump(by_alias=True, exclude_none=True)` behavior in `app/services/calendar_service.py` so `color_id` is emitted to Google as `colorId` automatically.

Update `_normalize_event` so responses include:

- `color_id`: current Google Calendar event color id when present

### Google client layer

No client changes are required in `app/google/calendar_client.py` because the Calendar API request body is already passed through directly for insert and patch operations.

## API shape

### Create or update input

Example payload fragment:

```json
{
  "event": {
    "summary": "Launch Review",
    "start": {"dateTime": "2026-03-13T09:00:00Z"},
    "end": {"dateTime": "2026-03-13T10:00:00Z"},
    "colorId": "11"
  }
}
```

### Normalized response

Example response fragment:

```json
{
  "id": "evt-2",
  "summary": "Launch Review",
  "color_id": "11"
}
```

## Error handling

- no special color-specific service errors are added in this iteration
- invalid provider-side color values remain the responsibility of Google Calendar API validation
- missing `colorId` stays optional and does not affect existing calls

## Testing

Add unit coverage for:

- event normalization returning `color_id`
- create serialization including `colorId`
- update serialization including `colorId`

## Success criteria

- `calendar_create_event` accepts `event.colorId`
- `calendar_update_event` accepts `event.colorId`
- Google request bodies include `colorId` when provided
- normalized event responses expose `color_id`
- existing calendar tests continue to pass
