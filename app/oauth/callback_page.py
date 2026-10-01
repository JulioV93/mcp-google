from html import escape

from starlette.responses import HTMLResponse


RESULTS = {
    "connected": (
        "Tu cuenta de Google está conectada",
        "Google MCP ya puede utilizar los permisos que aceptaste para esta cuenta.",
        "Ya puedes cerrar esta pestaña.",
        "Conexión completada",
        "✓",
    ),
    "cancelled": (
        "Cancelaste la conexión",
        "Esta solicitud terminó sin conectar tu cuenta de Google.",
        "Si quieres intentarlo de nuevo, solicita un enlace de conexión nuevo.",
        "Conexión cancelada",
        "−",
    ),
    "invalid": (
        "El enlace ya no es válido",
        "La autorización caducó, ya se utilizó o no contiene los datos necesarios.",
        "Solicita un enlace de conexión nuevo y vuelve a intentarlo.",
        "Necesitas un enlace nuevo",
        "↻",
    ),
    "error": (
        "No pudimos conectar tu cuenta",
        "No fue posible completar la conexión con Google en este momento.",
        "Solicita un enlace nuevo. Si el problema continúa, contacta al administrador.",
        "Conexión no completada",
        "!",
    ),
}


def callback_page(result: str, *, status_code: int = 200, email: str | None = None) -> HTMLResponse:
    title, description, next_step, label, symbol = RESULTS[result]
    account = f'<p class="account">{escape(email)}</p>' if email else ""
    html = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{title} · Google MCP</title>
  <style>
    :root {{ color-scheme: light; --ink: #142e40; --muted: #496473;
      --green: #17664f; --paper: #f0f5f5; --line: #d9e5e4; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--paper); color: var(--ink);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      line-height: 1.6; min-height: 100svh; display: grid; place-items: center;
      padding: 32px 20px; }}
    main {{ width: min(100%, 640px); background: #fff; border: 1px solid var(--line);
      border-radius: 24px; overflow: hidden; }}
    header {{ padding: 24px 32px; border-bottom: 1px solid var(--line);
      display: flex; align-items: center; gap: 12px; font-weight: 650; }}
    .mark {{ width: 28px; height: 28px; display: grid; place-items: center;
      color: #fff; background: var(--ink); border-radius: 8px; font-size: 16px; }}
    section {{ padding: 40px 32px 36px; }}
    .symbol {{ width: 64px; height: 64px; border-radius: 50%; display: grid;
      place-items: center; background: #e8f4ee; color: var(--green);
      font-size: 32px; margin-bottom: 24px; }}
    .invalid .symbol, .error .symbol {{ background: #fff1df; color: #825109; }}
    .cancelled .symbol {{ background: #edf2f5; color: var(--muted); }}
    h1 {{ font-size: clamp(27px, 4vw, 36px); line-height: 1.2; letter-spacing: -.025em;
      margin: 0 0 18px; font-weight: 650; text-wrap: balance; }}
    p {{ margin: 0 0 18px; color: var(--muted); max-width: 54ch; }}
    .account {{ color: var(--ink); font-weight: 600; overflow-wrap: anywhere;
      padding: 12px 16px; background: var(--paper); border-radius: 10px; }}
    .next {{ margin-top: 26px; margin-bottom: 0; color: var(--ink); }}
    footer {{ border-top: 1px solid var(--line); padding: 18px 32px;
      color: var(--muted); font-size: 14px; }}
    @media (max-width: 420px) {{ header, footer {{ padding-left: 24px; padding-right: 24px; }}
      section {{ padding: 32px 24px; }} }}
  </style>
</head>
<body>
  <main class="{result}">
    <header><span class="mark" aria-hidden="true">G</span>Google MCP</header>
    <section aria-labelledby="result-title">
      <div class="symbol" aria-hidden="true">{symbol}</div>
      <h1 id="result-title">{title}</h1>
      <p>{description}</p>
      {account}
      <p class="next">{next_step}</p>
    </section>
    <footer>{label}</footer>
  </main>
</body>
</html>"""
    return HTMLResponse(html, status_code=status_code, headers={
        "Cache-Control": "no-store",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": (
            "default-src 'none'; style-src 'unsafe-inline'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
        ),
    })
