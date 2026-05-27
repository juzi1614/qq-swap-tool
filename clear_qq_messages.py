#!/usr/bin/env python3
"""QQ Chat Record Cleaner - clear all local messages for a QQ account."""

import argparse, os, shutil, subprocess, sys, time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

try:
    from sqlcipher3 import dbapi2 as sqlcipher
except ImportError:
    print("ERROR: sqlcipher3 not installed. Run: pip install sqlcipher3")
    sys.exit(1)


def find_qq_data_dir() -> str:
    candidates = []
    env_dir = os.environ.get("QQ_DATA_DIR", "")
    if env_dir: candidates.append(env_dir)
    userprofile = os.environ.get("USERPROFILE", "")
    if userprofile:
        candidates.append(os.path.join(userprofile, "Documents", "Tencent Files"))
        candidates.append(os.path.join(userprofile, "文档", "Tencent Files"))
        candidates.append(os.path.join(userprofile, "OneDrive", "Documents", "Tencent Files"))
        candidates.append(os.path.join(userprofile, "OneDrive", "文档", "Tencent Files"))
    for p in candidates:
        if os.path.isdir(p): return p
    return candidates[0] if candidates else ""


def _db_path(qq: str) -> str:
    return os.path.join(QQ_DATA_DIR, qq, "nt_qq", "nt_db", "nt_msg.db")


QQ_HEADER_SIZE = 1024
TARGET_TABLES = {
    "c2c_msg_table": "private msgs", "c2c_temp_msg_table": "temp msgs",
    "group_msg_table": "group msgs", "group_msg_flow_table": "group flow",
    "group_at_me_msg": "@me msgs", "msg_unread_info_table": "unread",
    "recent_contact_v3_table": "contacts", "recent_contact_delete_storage": "deleted",
}


def open_qq_db(path: str, key: str):
    if not os.path.exists(path): raise FileNotFoundError(f"Not found: {path}")
    with open(path, "rb") as f: raw = f.read()
    header, body = raw[:QQ_HEADER_SIZE], raw[QQ_HEADER_SIZE:]
    tmp = os.path.join(os.environ.get("TEMP", "."), "_qq_clear_tmp.db")
    with open(tmp, "wb") as f: f.write(body)
    conn = sqlcipher.connect(tmp)
    c = conn.cursor()
    c.execute(f'PRAGMA key = "{key}"')
    c.execute("PRAGMA cipher_page_size = 4096")
    c.execute("PRAGMA kdf_iter = 4000")
    c.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA1")
    c.execute('PRAGMA cipher = "aes-256-cbc"')
    try:
        c.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
    except Exception:
        conn.close(); os.remove(tmp)
        raise ValueError("Wrong key")
    return conn, header, tmp


def save_qq_db(conn, header: bytes, output_path: str) -> int:
    conn.commit(); conn.close()
    tmp = os.path.join(os.environ.get("TEMP", "."), "_qq_clear_tmp.db")
    with open(tmp, "rb") as f: body = f.read()
    for s in ("", "-wal", "-shm", "-first.material", "-last.material"):
        f = output_path + s
        if os.path.exists(f): os.remove(f)
    with open(output_path, "wb") as f: f.write(header + body)
    os.remove(tmp)
    return len(header) + len(body)


def table_row_count(conn, table: str) -> int:
    try: return conn.cursor().execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
    except: return -1


def clear_all_messages(conn, qq, db_path, dry_run=False):
    c = conn.cursor()
    results = {}
    for table in TARGET_TABLES:
        n = table_row_count(conn, table)
        if n > 0: results[table] = n

    total = sum(results.values())
    print(f"\n  Account: {qq}  DB: {db_path}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'DELETE'}")
    for t, n in results.items():
        print(f"  {t:<40} {n:>8,}")
    print(f"  {'Total':<40} {total:>8,}")

    if total == 0:
        print("\n  Database already empty.")
        return results
    if dry_run:
        print(f"\n  [DRY RUN] {total:,} records would be deleted. Use --confirm to execute.")
        return results

    confirm = input("\n  Type DELETE to confirm: ")
    if confirm != "DELETE":
        print("  Cancelled.")
        return results

    deleted = {}
    for table in TARGET_TABLES:
        try:
            n = c.execute(f"DELETE FROM [{table}]").rowcount
            if n > 0: deleted[table] = n; print(f"  [{table}] {n:,}")
        except Exception as e:
            print(f"  [{table}] skip: {e}")

    conn.commit()
    try: c.execute("VACUUM"); print("  VACUUM done")
    except Exception as e: print(f"  VACUUM skip: {e}")
    conn.commit()
    print(f"  Deleted {sum(deleted.values()):,} records.")
    return deleted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QQ Chat Record Cleaner")
    parser.add_argument("--qq", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--qq-data-dir", default=None)
    args = parser.parse_args()

    QQ_DATA_DIR = find_qq_data_dir()
    if args.qq_data_dir: QQ_DATA_DIR = args.qq_data_dir

    db = _db_path(args.qq)
    if not os.path.exists(db):
        print(f"ERROR: DB not found: {db}")
        sys.exit(1)

    subprocess.run(["taskkill", "/F", "/IM", "QQ.exe"], capture_output=True)
    time.sleep(1)

    backup = db + f".clear_backup_{int(time.time())}"
    shutil.copy2(db, backup)
    print(f"Backup: {os.path.basename(backup)}")

    conn, header, tmp = open_qq_db(db, args.key)
    try:
        dry = args.dry_run or not args.confirm
        deleted = clear_all_messages(conn, args.qq, db, dry_run=dry)
        if not dry and deleted:
            save_qq_db(conn, header, db)
            print(f"Saved. Backup: {os.path.basename(backup)}")
    finally:
        try: conn.close()
        except: pass
        if os.path.exists(tmp): os.remove(tmp)
