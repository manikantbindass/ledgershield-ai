"""Create local-only API tokens without printing them. Never commit .env."""
from pathlib import Path
import secrets

if __name__ == "__main__":
    path = Path(__file__).resolve().parents[1] / ".env"
    content = path.read_text() if path.exists() else "RECOVERY_MODE=observe_only\n"
    for role in ("OPERATOR", "ADMIN"):
        name = f"LEDGERSHIELD_{role}_TOKEN"
        lines = content.splitlines()
        matches = [i for i, line in enumerate(lines) if line.startswith(name + "=")]
        if not matches:
            content = content.rstrip() + f"\n{name}={secrets.token_urlsafe(36)}\n"
        elif not lines[matches[0]].split("=", 1)[1].strip():
            lines[matches[0]] = f"{name}={secrets.token_urlsafe(36)}"
            content = "\n".join(lines) + "\n"
    path.write_text(content, newline="\n")
    print("Local credentials saved to .env (ignored by Git). No tokens were printed.")
