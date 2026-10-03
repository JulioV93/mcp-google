"""Local administrator utility. Credentials are written to files, never printed."""

import argparse
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from cryptography.fernet import Fernet
from dotenv import dotenv_values, load_dotenv, set_key

from app.config import WRITE_TOOLS, Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, default=Path(".env"))
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("init", help="Fill missing internal keys without rotating existing keys")
    issue = commands.add_parser(
        "issue-token",
        help="Issue an MCP JWT: one hour, or no expiration when JWT_ALLOW_NON_EXPIRING_TOKENS=true",
    )
    issue.add_argument(
        "--subject", required=True, help="Stable, distinct MCP identity for each person"
    )
    issue.add_argument(
        "--tenant-id", help="Tenant identity; omit for the legacy no-tenant namespace"
    )
    issue.add_argument("--approve-tool", action="append", default=[], choices=sorted(WRITE_TOOLS))
    issue.add_argument("--output", type=Path, required=True)
    for action in ("get-access", "set-access"):
        access = commands.add_parser(action, help="Inspect or provision persistent identity access")
        access.add_argument("--subject", required=True)
        access.add_argument("--tenant-id")
        if action == "set-access":
            access.add_argument(
                "--profile", required=True, choices=["read_only", "read_write", "disabled"]
            )
    args = parser.parse_args()

    if args.action == "init":
        if not args.env.is_file():
            parser.error("Create the environment file from the deployment template first")
        args.env.chmod(0o600)
        values = dotenv_values(args.env)
        for name, factory in (
            ("TOKEN_ENCRYPTION_KEY", lambda: Fernet.generate_key().decode()),
            ("JWT_SHARED_SECRET", lambda: secrets.token_urlsafe(48)),
        ):
            if not values.get(name):
                set_key(args.env, name, factory())
        print("Internal keys saved; existing keys preserved.")
        return

    if not args.subject.strip() or len(args.subject) > 255:
        parser.error("Subject must be nonempty and at most 255 characters")
    if args.tenant_id is not None and (not args.tenant_id.strip() or len(args.tenant_id) > 255):
        parser.error("Tenant must be nonempty and at most 255 characters")
    load_dotenv(args.env, override=True)
    settings = Settings(_env_file=None)
    if args.action in {"get-access", "set-access"}:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from app.db.repositories.users import UserRepository
        from app.services.audit_service import AuditService

        engine = create_engine(settings.database_url)
        try:
            with Session(engine) as session:
                users = UserRepository(session)
                user = users.get_by_external_subject(args.subject, args.tenant_id)
                previous = user.access_profile if user else "read_only"
                if args.action == "set-access":
                    user = user or users.create(args.subject, args.tenant_id)
                    user.access_profile = args.profile
                    # Policy and its administrative audit are committed atomically.
                    AuditService(session).record_tool_call(
                        external_subject=args.subject,
                        tenant_id=args.tenant_id,
                        tool_name="admin_set_access",
                        provider="local",
                        resource_type="authorization",
                        arguments={"previous_profile": previous, "access_profile": args.profile},
                        result_status="success",
                    )
                print(
                    json.dumps(
                        {
                            "subject": args.subject,
                            "tenant_id": args.tenant_id,
                            "access_profile": user.access_profile if user else "read_only",
                            "provisioned": user is not None,
                        }
                    )
                )
        finally:
            engine.dispose()
        return
    if settings.jwt_test_mode or settings.jwt_algorithm_list != ["HS256"]:
        parser.error("Use JWT_TEST_MODE=false and JWT_ALGORITHMS=HS256")
    if not settings.jwt_shared_secret or len(settings.jwt_shared_secret.encode()) < 32:
        parser.error("Configure a signing secret of at least 32 bytes")
    now = datetime.now(UTC)
    claims = {
        "sub": args.subject,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
    }
    if not settings.jwt_allow_non_expiring_tokens:
        claims["exp"] = now + timedelta(hours=1)
    if args.tenant_id is not None:
        claims["tenant_id"] = args.tenant_id
    if args.approve_tool:
        claims["approved_tools"] = list(dict.fromkeys(args.approve_tool))
    token = jwt.encode(claims, settings.jwt_shared_secret, algorithm="HS256")
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write(token + "\n")
    print(f"JWT saved in protected file: {args.output}")


if __name__ == "__main__":
    main()
