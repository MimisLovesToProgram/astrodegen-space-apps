"""Set up the local PocketBase demo while preserving existing users and data."""

import argparse
import json
import os
import secrets
import socket
import sqlite3
import subprocess
import time
import uuid
from pathlib import Path

from .config import read_settings
from .pocketbase import PocketBaseTelemetry


def _private_file(path, mode="w"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if mode == "a" else os.O_EXCL)
    descriptor = os.open(path, flags, 0o600)
    os.chmod(path, 0o600)
    return os.fdopen(descriptor, mode)


def setup_local(binary=None, data_dir=None, env_dir=None, port=8090, keep_running=True):
    root = Path(__file__).resolve().parents[2]
    backend = root / "backend/pocketbase"
    binary = Path(binary or backend / "pocketbase").resolve()
    data_dir = Path(data_dir or backend / "pb_data").resolve()
    env_dir = Path(env_dir or root).resolve()
    if not binary.is_file():
        raise ValueError("Place the PocketBase executable in backend/pocketbase first")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    # Refuse to migrate or reconfigure a server that may belong to another run.
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise ValueError(f"Port {port} is already in use; stop that server or choose another port")
    env_dir.mkdir(parents=True, exist_ok=True)
    url = f"http://127.0.0.1:{port}"
    credentials = {}
    for role in ("ingest", "worker", "reader"):
        path = env_dir / (".env" if role == "worker" else ".env." + role)
        if path.exists():
            settings = read_settings(path)
            if settings.get("POCKETBASE_URL") != url or not settings.get("POCKETBASE_EMAIL") or not settings.get("POCKETBASE_PASSWORD"):
                raise ValueError(f"Existing settings need manual review: {path}")
            if settings.get("POCKETBASE_TOKEN"):
                raise ValueError(f"Remove or review the existing token before setup: {path}")
        else:
            settings = {"POCKETBASE_URL": url,
                        "POCKETBASE_EMAIL": f"astrocrates-{role}@example.invalid",
                        "POCKETBASE_PASSWORD": secrets.token_urlsafe(32)}
        credentials[role] = (path, settings)
    log_path = env_dir / "data/pocketbase-setup.log"
    # Keep a consistent snapshot before changing an existing database. SQLite's
    # backup API includes committed WAL data without copying an active WAL file.
    existing_database = data_dir / "data.db"
    backup_path = env_dir / "data/backups/pocketbase-before-step2.db"
    if existing_database.exists() and not backup_path.exists():
        temporary_backup = backup_path.with_suffix(".partial")
        with _private_file(temporary_backup):
            pass
        with sqlite3.connect("file:" + str(existing_database) + "?mode=ro", uri=True) as source:
            with sqlite3.connect(temporary_backup) as destination:
                source.backup(destination)
        os.replace(temporary_backup, backup_path)
    options = ["--dir", str(data_dir), "--migrationsDir", str(backend / "pb_migrations"), "--dev=false"]
    temporary_email = "setup-" + uuid.uuid4().hex + "@example.invalid"
    temporary_password = secrets.token_urlsafe(32)
    process = None
    admin = PocketBaseTelemetry(url)
    temporary_id = None
    created_admin = False
    completed = False
    with _private_file(log_path, "a") as log:
        try:
            subprocess.run([str(binary), "migrate", "up", *options], check=True, stdout=log, stderr=log)
            # Preserve the existing administrator. On a fresh installation the
            # owner must create the first administrator before service setup.
            with sqlite3.connect("file:" + str(data_dir / "data.db") + "?mode=ro", uri=True) as connection:
                admin_count = connection.execute("SELECT count(*) FROM _superusers").fetchone()[0]
            if not admin_count:
                raise ValueError("Create the initial PocketBase administrator before running service setup")
            subprocess.run([str(binary), "superuser", "create", temporary_email, temporary_password, *options],
                           check=True, stdout=log, stderr=log)
            created_admin = True
            process = subprocess.Popen(
                [str(binary), "serve", "--http", f"127.0.0.1:{port}", *options,
                 "--hooksDir", str(backend / "pb_hooks"), "--hooksWatch=false"],
                cwd=backend, stdout=log, stderr=log, start_new_session=True,
            )
            for attempt in range(100):
                if process.poll() is not None:
                    raise RuntimeError(f"PocketBase failed to start; inspect {log_path}")
                try:
                    admin.request("GET", "/api/health")
                    break
                except OSError:
                    if attempt == 99:
                        raise RuntimeError("PocketBase startup timed out") from None
                    time.sleep(0.1)
            temporary_id = admin.authenticate(temporary_email, temporary_password, "_superusers")["id"]
            for role, (path, settings) in credentials.items():
                records = admin.request("GET", "/api/collections/telemetry_services/records", query={
                    "filter": "email=" + json.dumps(settings["POCKETBASE_EMAIL"]), "perPage": 1,
                })["items"]
                if records:
                    if records[0]["role"] != role:
                        raise ValueError(f"Existing account has a different role: {role}")
                else:
                    # Save recoverable credentials before creating the account.
                    if not path.exists():
                        with _private_file(path) as handle:
                            for key, value in settings.items():
                                handle.write(key + "=" + json.dumps(value) + "\n")
                    admin.request("POST", "/api/collections/telemetry_services/records", {
                        "email": settings["POCKETBASE_EMAIL"], "password": settings["POCKETBASE_PASSWORD"],
                        "passwordConfirm": settings["POCKETBASE_PASSWORD"], "role": role,
                    })
                service = PocketBaseTelemetry(url)
                service.authenticate(settings["POCKETBASE_EMAIL"], settings["POCKETBASE_PASSWORD"])
                if not path.exists():
                    with _private_file(path) as handle:
                        for key, value in settings.items():
                            handle.write(key + "=" + json.dumps(value) + "\n")
                os.chmod(path, 0o600)
            admin.request("DELETE", "/api/collections/_superusers/records/" + temporary_id)
            created_admin = False
            completed = True
        finally:
            if process is not None and (not completed or not keep_running):
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if created_admin:
                # A failed setup must not leave its temporary administrator.
                subprocess.run([str(binary), "superuser", "delete", temporary_email, *options],
                               check=True, stdout=log, stderr=log)
    if keep_running:
        pid_path = env_dir / "data/pocketbase.pid"
        pid_path.write_text(str(process.pid) + "\n")
    return {"url": url, "server_running": keep_running,
            "pid": process.pid if keep_running else None,
            "service_roles": list(credentials),
            "credential_files": [str(value[0]) for value in credentials.values()],
            "log": str(log_path), "backup": str(backup_path) if backup_path.exists() else None,
            "temporary_admin_removed": True}


def main():
    parser = argparse.ArgumentParser(description="Configure the local Astrocrates PocketBase backend")
    parser.add_argument("--binary")
    parser.add_argument("--data-dir")
    parser.add_argument("--env-dir")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--stop-after-setup", action="store_true")
    args = parser.parse_args()
    print(json.dumps(setup_local(args.binary, args.data_dir, args.env_dir, args.port,
                                keep_running=not args.stop_after_setup), indent=2))


if __name__ == "__main__":
    main()
