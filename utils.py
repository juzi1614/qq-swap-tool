"""QQ chat record utility functions."""
import hashlib, os


def md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def compute_key(uid: str, rand: str) -> str:
    return md5(md5(uid) + rand)


def compute_path_hash(uid: str) -> str:
    return md5(md5(uid) + "nt_kernel")


def open_qq_db(db_path: str, key: str):
    from sqlcipher3 import dbapi2 as sqlcipher
    conn = sqlcipher.connect(db_path)
    c = conn.cursor()
    c.execute(f"PRAGMA key = '{key}'")
    c.execute("PRAGMA cipher_page_size = 4096")
    c.execute("PRAGMA kdf_iter = 4000")
    c.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA1")
    c.execute("PRAGMA cipher_default_kdf_algorithm = PBKDF2_HMAC_SHA512")
    c.execute('PRAGMA cipher = "aes-256-cbc"')
    return conn


def strip_header(src_path: str, dst_path: str) -> int:
    with open(src_path, "rb") as f: data = f.read()
    with open(dst_path, "wb") as f: f.write(data[1024:])
    return len(data[1024:])


def add_header(src_path: str, dst_path: str, rand: str) -> int:
    header = bytearray(1024)
    magic = b"SQLite header 3\x00"
    header[0:16] = magic
    header[16:18] = (4096).to_bytes(2, "big")
    marker = b"QQ_NT DB"
    header[32:32 + len(marker)] = marker
    rand_bytes = rand.encode("utf-8")
    header[32 + len(marker) + 1:32 + len(marker) + 1 + len(rand_bytes)] = rand_bytes
    with open(src_path, "rb") as f: data = f.read()
    with open(dst_path, "wb") as f:
        f.write(bytes(header))
        f.write(data)
    return 1024 + len(data)
