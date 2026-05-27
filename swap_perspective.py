#!/usr/bin/env python3
"""QQ Chat Perspective Swap Tool v3.1 (Portable)"""

import argparse, os, re, shutil, subprocess, sys, time
from typing import Optional

try:
    from sqlcipher3 import dbapi2 as sqlcipher
except ImportError:
    print("ERROR: sqlcipher3 is not installed. Run: pip install sqlcipher3")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(os.environ.get("TEMP", SCRIPT_DIR), "qq_swap_temp")
BUNDLED_KEY_SCRIPT = os.path.join(SCRIPT_DIR, "windows_ntqq_get_key.ps1")


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


QQ_DATA_DIR = find_qq_data_dir()


def _open_db(path: str, key: str):
    if not os.path.exists(path): raise FileNotFoundError(f"Database not found: {path}")
    conn = sqlcipher.connect(path)
    c = conn.cursor()
    c.execute(f'PRAGMA key = "{key}"')
    c.execute("PRAGMA cipher_page_size = 4096")
    c.execute("PRAGMA kdf_iter = 4000")
    c.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA1")
    c.execute('PRAGMA cipher = "aes-256-cbc"')
    return conn


def _strip_header(src: str, dst: str):
    with open(src, "rb") as f: data = f.read()
    with open(dst, "wb") as f: f.write(data[1024:])
    return len(data) - 1024


def _db_path(qq: str) -> str:
    return os.path.join(QQ_DATA_DIR, qq, "nt_qq", "nt_db", "nt_msg.db")


def find_uid(conn, qq: str) -> Optional[str]:
    c = conn.cursor()
    for val in (qq, int(qq)):
        try:
            row = c.execute("SELECT [48902] FROM nt_uid_mapping_table WHERE [1002]=?", (val,)).fetchone()
            if row and row[0]: return row[0]
        except: pass
    for val in (qq, int(qq)):
        try:
            row = c.execute("SELECT [1000] FROM profile_info_v2 WHERE [1002]=?", (val,)).fetchone()
            if row and row[0]: return row[0]
        except: pass
    try:
        row = c.execute("SELECT [40020], COUNT(*) c FROM c2c_msg_table WHERE [40020]!=[40021] AND [40020]!='' GROUP BY [40020] ORDER BY c DESC LIMIT 1").fetchone()
        if row and row[0]: return row[0]
    except: pass
    return None


def swap_conversation(conn, source_uid, target_uid, right_uid, output_uid, peer_uid):
    c = conn.cursor()
    count = c.execute("SELECT COUNT(*) FROM c2c_msg_table WHERE [40021]=?", (target_uid,)).fetchone()[0]
    if count == 0: return 0
    c.execute("UPDATE c2c_msg_table SET [40020]=? WHERE [40021]=? AND [40020]=?", (output_uid, target_uid, right_uid))
    c.execute("UPDATE c2c_msg_table SET [40021]=? WHERE [40021]=?", (peer_uid, target_uid))
    c.execute("UPDATE c2c_msg_table SET [40013]=0 WHERE [40020]!=?", (output_uid,))
    c.execute("UPDATE c2c_msg_table SET [40013]=2 WHERE [40020]=?", (output_uid,))
    return count


def clean_database(conn, keep_peer):
    c = conn.cursor()
    c.execute("DELETE FROM c2c_msg_table WHERE [40021]!=?", (keep_peer,))
    c.execute("DELETE FROM c2c_temp_msg_table")
    for t in ("group_msg_table","group_msg_flow_table","group_at_me_msg","msg_unread_info_table","recent_contact_v3_table","recent_contact_delete_storage"):
        try: c.execute(f"DELETE FROM {t}")
        except: pass


def fix_recent_contact(conn, peer_uid, peer_qq, display_name, target_uid_for_template):
    c = conn.cursor()
    schema = c.execute("SELECT sql FROM sqlite_master WHERE name='recent_contact_v3_table'").fetchone()[0]
    rc_cols = re.findall(r"\[(\d+)\]", schema)
    ref = c.execute("SELECT * FROM recent_contact_v3_table WHERE [40021]=?", (target_uid_for_template,)).fetchone()
    last = c.execute("SELECT [40001],[40020],[40050] FROM c2c_msg_table WHERE [40021]=? ORDER BY [40050] DESC LIMIT 1", (peer_uid,)).fetchone()
    total = c.execute("SELECT COUNT(*) FROM c2c_msg_table WHERE [40021]=?", (peer_uid,)).fetchone()[0]
    if not last: return
    c.execute("DELETE FROM recent_contact_v3_table WHERE [40021]=?", (peer_uid,))
    if ref:
        rc = list(ref)
        for i, col in enumerate(rc_cols):
            if col == "40021": rc[i] = peer_uid
            elif col == "40030": rc[i] = int(peer_qq)
            elif col == "40033": rc[i] = int(peer_qq)
            elif col == "40020": rc[i] = last[1]
            elif col == "40001": rc[i] = last[0]
            elif col == "41102": rc[i] = last[0]
            elif col == "40050": rc[i] = last[2]
            elif col == "41136": rc[i] = last[2]
            elif col == "40003": rc[i] = total
            elif col == "40005": rc[i] = total
            elif col == "40093": rc[i] = display_name
            elif col == "40094": rc[i] = display_name
            elif col == "40095": rc[i] = ""
            elif col == "41110": rc[i] = ""
        ph = ",".join(["?" for _ in rc_cols])
        cl = ",".join([f"[{c}]" for c in rc_cols])
        c.execute(f"INSERT INTO recent_contact_v3_table ({cl}) VALUES ({ph})", rc)
    else:
        c.execute("INSERT INTO recent_contact_v3_table ([40055],[40010],[40027],[40021],[40030],[40041],[41102],[40020],[40050],[40001],[40093],[40094],[40011],[41136],[40003],[40005],[40033],[40002],[40006]) VALUES (1,1,1,?,?,2,?,?,?,?,?,?,2,?,?,?,?,?,?)",
            (peer_uid,int(peer_qq),last[0],last[1],last[2],last[0],display_name,display_name,last[2],total,total,int(peer_qq),total,total))


def deploy(source_qq, target_qq, output_qq, peer_qq, right_qq, source_key, output_key):
    if not os.path.isdir(QQ_DATA_DIR):
        print(f"ERROR: QQ data directory not found: {QQ_DATA_DIR}")
        sys.exit(1)
    subprocess.run(["taskkill","/F","/IM","QQ.exe"], capture_output=True)
    time.sleep(1)
    os.makedirs(TEMP_DIR, exist_ok=True)

    output_db = _db_path(output_qq)
    if not os.path.exists(os.path.dirname(output_db)):
        print(f"ERROR: Output QQ directory not found for {output_qq}")
        sys.exit(1)

    backup_path = output_db + f".backup_{int(time.time())}"
    if os.path.exists(output_db):
        shutil.copy2(output_db, backup_path)
        print(f"[1/7] Backup: {os.path.basename(backup_path)}")

    print("[2/7] Reading source database...")
    source_db = _db_path(source_qq)
    if not os.path.exists(source_db):
        print(f"ERROR: Source DB not found: {source_db}")
        sys.exit(1)

    work_path = os.path.join(TEMP_DIR, "work.db")
    size = _strip_header(source_db, work_path)
    print(f"  {size:,} bytes")
    conn = _open_db(work_path, source_key)

    print("[3/7] Resolving UIDs...")
    source_uid = find_uid(conn, source_qq)
    target_uid = find_uid(conn, target_qq)
    right_uid = find_uid(conn, right_qq) if right_qq != output_qq else None

    output_uid = find_uid(conn, output_qq)
    if not output_uid and output_qq != source_qq:
        out_db = _db_path(output_qq)
        if os.path.exists(out_db):
            tmp_out = os.path.join(TEMP_DIR, "out_uid.db")
            _strip_header(out_db, tmp_out)
            conn_out = _open_db(tmp_out, output_key)
            output_uid = find_uid(conn_out, output_qq)
            conn_out.close()
            os.remove(tmp_out)
    if not output_uid:
        print(f"ERROR: Cannot find UID for output QQ {output_qq}")
        sys.exit(1)
    if right_qq == output_qq: right_uid = output_uid
    if not right_uid:
        print(f"ERROR: Cannot find UID for right QQ {right_qq}")
        sys.exit(1)

    peer_uid = find_uid(conn, peer_qq)
    if not peer_uid and peer_qq != output_qq:
        out_db = _db_path(output_qq)
        if os.path.exists(out_db):
            tmp_out = os.path.join(TEMP_DIR, "peer_uid.db")
            _strip_header(out_db, tmp_out)
            conn_out = _open_db(tmp_out, output_key)
            peer_uid = find_uid(conn_out, peer_qq)
            conn_out.close()
            os.remove(tmp_out)
    if not peer_uid:
        print(f"ERROR: Cannot find UID for peer QQ {peer_qq}")
        sys.exit(1)

    print(f"  Source: {source_uid}\n  Target conv: {target_uid}\n  Output: {output_uid}\n  Peer: {peer_uid}\n  Right: {right_uid}")

    print("[4/7] Swapping conversation...")
    count = swap_conversation(conn, source_uid, target_uid, right_uid, output_uid, peer_uid)
    if count == 0:
        print("ERROR: No messages found for this conversation")
        sys.exit(1)
    print(f"  {count} messages swapped")

    print("[5/7] Cleaning database...")
    clean_database(conn, peer_uid)
    final = conn.cursor().execute("SELECT COUNT(*) FROM c2c_msg_table").fetchone()[0]
    print(f"  {final} messages remaining")

    print("[6/7] Updating recent contact...")
    fix_recent_contact(conn, peer_uid, peer_qq, str(source_qq), target_uid)
    conn.commit()
    rc = conn.cursor().execute("SELECT COUNT(*) FROM recent_contact_v3_table").fetchone()[0]
    print(f"  {rc} recent contact(s)")

    print("[7/7] Deploying...")
    conn.cursor().execute(f'PRAGMA rekey = "{output_key}"')
    conn.commit()
    conn.close()

    for s in ("","-wal","-shm","-first.material","-last.material"):
        f = output_db + s
        if os.path.exists(f): os.remove(f)

    with open(work_path, "rb") as f: encrypted = f.read()
    with open(backup_path, "rb") as f: header = f.read(1024)
    with open(output_db, "wb") as f: f.write(header + encrypted)
    os.remove(work_path)

    print(f"\n{'='*50}")
    print(f"Done! {final} messages deployed.")
    print(f"Output: {output_qq} | Peer area: {peer_qq}")
    print(f"RIGHT side: {right_qq} | LEFT side: the other party")
    print(f"Backup: {os.path.basename(backup_path)}")
    print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(description="QQ Chat Perspective Swap Tool v3.1")
    parser.add_argument("--source-qq", required=True)
    parser.add_argument("--target-qq", required=True)
    parser.add_argument("--output-qq", required=True)
    parser.add_argument("--peer-qq", required=True)
    parser.add_argument("--right-qq", required=True)
    parser.add_argument("--source-key", required=True)
    parser.add_argument("--output-key", required=True)
    parser.add_argument("--qq-data-dir", default=None)
    args = parser.parse_args()
    if args.qq_data_dir:
        global QQ_DATA_DIR
        QQ_DATA_DIR = args.qq_data_dir
    deploy(args.source_qq, args.target_qq, args.output_qq, args.peer_qq, args.right_qq, args.source_key, args.output_key)


if __name__ == "__main__":
    main()
