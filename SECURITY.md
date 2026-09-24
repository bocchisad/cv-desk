# Security

CV Desk controls system media keys, Mission Control / Spaces, volume, and can capture the screen.

## Permissions

On macOS, grant **Camera**, **Accessibility**, and **Screen Recording** to the process that actually runs the app — typically **Python** from your venv, or **Terminal** / your IDE — not necessarily the optional `CV Desk.app` shell wrapper.

## Trust boundaries

- Config: `~/Library/Application Support/CVDesk/config.json` (local only)
- Hand model: downloaded once to `models/hand_landmarker.task` over HTTPS (verified TLS)
- No network calls at runtime after the model is present (except optional MediaPipe telemetry noise)

## Reporting

Open a GitHub issue for security-relevant bugs. Do not attach private screenshots with sensitive desktop content.
