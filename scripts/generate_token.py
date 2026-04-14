"""
Genera un token JWT estático para consumir el API.

Uso:
    python scripts/generate_token.py
    python scripts/generate_token.py --subject mi-sistema --days 180

El token resultante se entrega al consumidor del API.
Se usa como: Authorization: Bearer <token>
"""

import argparse
import sys
from pathlib import Path

# Permite ejecutar desde la raíz del proyecto sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.security import create_access_token


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a static API JWT token")
    parser.add_argument(
        "--subject",
        default=settings.SYSTEM_CLIENT_ID,
        help=f"Token subject (default: {settings.SYSTEM_CLIENT_ID})",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=settings.JWT_ACCESS_TOKEN_EXPIRE_DAYS,
        help=f"Token validity in days (default: {settings.JWT_ACCESS_TOKEN_EXPIRE_DAYS})",
    )
    args = parser.parse_args()

    # Temporarily override expiry for this generation if --days was passed.
    if args.days != settings.JWT_ACCESS_TOKEN_EXPIRE_DAYS:
        settings.__dict__["JWT_ACCESS_TOKEN_EXPIRE_DAYS"] = args.days

    token = create_access_token(subject=args.subject)

    print("\n=== TOOL_API — Static Bearer Token ===")
    print(f"Subject : {args.subject}")
    print(f"Validity: {args.days} days")
    print(f"\nToken:\n{token}\n")
    print("Usage:  Authorization: Bearer <token>")
    print("======================================\n")


if __name__ == "__main__":
    main()
