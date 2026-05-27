#!/usr/bin/env python3
"""QQ Chat Perspective Swap Tool - GUI (Portable)"""

import os
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, scrolledtext

# Resolve paths correctly for both PyInstaller (frozen) and normal Python
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = sys._MEIPASS
    EXE_DIR = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXE_DIR = BUNDLE_DIR

sys.path.insert(0, BUNDLE_DIR)

_ps1_bundled = os.path.join(BUNDLE_DIR, "windows_ntqq_get_key.ps1")
_ps1_external = os.path.join(EXE_DIR, "windows_ntqq_get_key.ps1")
KEY_SCRIPT = _ps1_bundled if os.path.exists(_ps1_bundled) else _ps1_external

from swap_perspective import deploy, _db_path, find_qq_data_dir, QQ_DATA_DIR


def extract_key(output_file: str) -> str:
    if not os.path.exists(KEY_SCRIPT):
        return None
    cmd = f'powershell -ExecutionPolicy Bypass -File "{KEY_SCRIPT}" > "{output_file}" 2>&1'
    try:
        subprocess.run(cmd, shell=True, timeout=300)
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass

    for enc in ["utf-8", "gbk", "utf-16", "latin-1"]:
        try:
            with open(output_file, "r", encoding=enc, errors="ignore") as f:
                text = f.read()
            match = re.search(r"加密密钥:\s+(\S{16})", text)
            if match:
                return match.group(1)
            match = re.search(r"找到密钥:\s+(\S{16})", text)
            if match:
                return match.group(1)
        except Exception:
            continue
    return None


class App:
    def __init__(self, root):
        self.root = root
        root.title("QQ 聊天记录视角互换工具 v3.1")
        root.geometry("620x680")
        root.resizable(False, False)

        style = ttk.Style()
        style.theme_use("clam")

        main = ttk.Frame(root, padding=15)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="账号配置", font=("", 11, "bold")).pack(anchor="w", pady=(0, 5))

        self._row(main, "源账号 (提供聊天记录):", "source_qq", "")
        self._row(main, "目标对话 (要互换的对话):", "target_qq", "")
        self._row(main, "输出账号 (部署到谁):", "output_qq", "")
        f = ttk.Frame(main)
        f.pack(fill="x", pady=2)
        ttk.Label(f, text="显示区域 (哪个聊天区域):", width=28).pack(side="left")
        self.peer_qq = tk.StringVar(value="")
        ttk.Entry(f, textvariable=self.peer_qq, width=22).pack(side="left")
        ttk.Label(f, text="(须输出账号无服务器记录)", foreground="gray", font=("", 8)).pack(side="left", padx=5)

        f = ttk.Frame(main)
        f.pack(fill="x", pady=2)
        ttk.Label(f, text="右侧显示 (谁当\"我\"):", width=28).pack(side="left")
        self.right_qq = tk.StringVar(value="")
        ttk.Entry(f, textvariable=self.right_qq, width=22).pack(side="left")

        ttk.Label(main, text="数据目录", font=("", 11, "bold")).pack(anchor="w", pady=(15, 5))
        dd_frame = ttk.Frame(main)
        dd_frame.pack(fill="x", pady=2)
        self.qq_data_dir = tk.StringVar(value=QQ_DATA_DIR)
        ttk.Label(dd_frame, text="QQ数据目录:", width=28).pack(side="left")
        ttk.Entry(dd_frame, textvariable=self.qq_data_dir, width=50).pack(side="left")
        if not os.path.isdir(QQ_DATA_DIR):
            ttk.Label(dd_frame, text="未找到!", foreground="red").pack(side="left", padx=5)

        ttk.Label(main, text="密钥配置", font=("", 11, "bold")).pack(anchor="w", pady=(15, 5))

        if not os.path.exists(KEY_SCRIPT):
            ttk.Label(main, text="警告: 未找到密钥提取脚本 (windows_ntqq_get_key.ps1)", foreground="red").pack(anchor="w")

        kf1 = ttk.Frame(main)
        kf1.pack(fill="x", pady=2)
        ttk.Label(kf1, text="源账号密钥:", width=28).pack(side="left")
        self.source_key = tk.StringVar()
        sk_entry = ttk.Entry(kf1, textvariable=self.source_key, width=22, show="*")
        sk_entry.pack(side="left")
        self.sk_entry = sk_entry
        self.src_key_btn = ttk.Button(kf1, text="获取", width=6, command=lambda: self._get_key("源账号", self.source_key))
        self.src_key_btn.pack(side="left", padx=5)
        self.src_key_status = ttk.Label(kf1, text="", foreground="gray")
        self.src_key_status.pack(side="left")

        kf2 = ttk.Frame(main)
        kf2.pack(fill="x", pady=2)
        ttk.Label(kf2, text="输出账号密钥:", width=28).pack(side="left")
        self.output_key = tk.StringVar()
        ok_entry = ttk.Entry(kf2, textvariable=self.output_key, width=22, show="*")
        ok_entry.pack(side="left")
        self.ok_entry = ok_entry
        self.out_key_btn = ttk.Button(kf2, text="获取", width=6, command=lambda: self._get_key("输出账号", self.output_key))
        self.out_key_btn.pack(side="left", padx=5)
        self.out_key_status = ttk.Label(kf2, text="", foreground="gray")
        self.out_key_status.pack(side="left")

        self.show_keys = tk.BooleanVar()
        ttk.Checkbutton(main, text="显示密钥", variable=self.show_keys, command=self._toggle_keys).pack(anchor="w")

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x", pady=(15, 10))

        self.run_btn = ttk.Button(btn_frame, text="开始互换", command=self._run)
        self.run_btn.pack(side="left", padx=(0, 5))
        self.restore_btn = ttk.Button(btn_frame, text="恢复数据库", command=self._restore)
        self.restore_btn.pack(side="left", padx=5)
        self.stop_btn = ttk.Button(btn_frame, text="停止", command=self._stop, state="disabled")
        self.stop_btn.pack(side="left", padx=5)
        ttk.Button(btn_frame, text="清空日志", command=self._clear_log).pack(side="right")

        ttk.Label(main, text="运行日志", font=("", 11, "bold")).pack(anchor="w", pady=(10, 5))
        self.log = scrolledtext.ScrolledText(main, height=13, state="disabled", font=("Consolas", 9))
        self.log.pack(fill="both", expand=True)

        self.progress = ttk.Progressbar(main, mode="indeterminate")
        self.progress.pack(fill="x", pady=(8, 0))
        self.status = ttk.Label(main, text="就绪", foreground="gray")
        self.status.pack(anchor="w")
        self._running = False

    def _row(self, parent, label, attr, default=""):
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=2)
        ttk.Label(f, text=label, width=28).pack(side="left")
        var = tk.StringVar(value=default)
        setattr(self, attr, var)
        ttk.Entry(f, textvariable=var, width=22).pack(side="left")

    def _get_key(self, name, var):
        if self._running: return
        if not os.path.exists(KEY_SCRIPT):
            messagebox.showerror("错误", "未找到密钥提取脚本。\n请确保 windows_ntqq_get_key.ps1 与本程序在同一目录。")
            return

        btn = self.src_key_btn if name == "源账号" else self.out_key_btn
        status = self.src_key_status if name == "源账号" else self.out_key_status

        ok = messagebox.askokcancel(f"获取{name}密钥",
            f"请确保QQ已完全关闭。\n\n点击确定后：\n1. QQ窗口会自动弹出\n2. 请在QQ窗口登录 **{name}**\n3. 登录后软件自动获取密钥\n\n继续？")
        if not ok: return

        btn.configure(state="disabled")
        status.configure(text="等待登录...", foreground="blue")
        self.progress.start()
        self._log(f"[获取密钥] {name} - 请在弹出的QQ窗口登录 {name}")

        def run():
            out_file = os.path.join(os.path.dirname(KEY_SCRIPT), "_key_output.txt")
            key = extract_key(out_file)
            try: os.remove(out_file)
            except: pass

            if key:
                self.root.after(0, lambda: var.set(key))
                self.root.after(0, lambda: status.configure(text="已获取", foreground="green"))
                self.root.after(0, lambda: self._log(f"[获取密钥] {name} 成功"))
            else:
                self.root.after(0, lambda: status.configure(text="失败", foreground="red"))
                self.root.after(0, lambda: self._log(f"[获取密钥] {name} 失败 - 请重试"))
                self.root.after(0, lambda: messagebox.showerror("失败",
                    "未能获取密钥。请确认：\n1. QQ已完全关闭\n2. 在弹出的QQ窗口登录了正确的账号\n3. 登录后在QQ主界面停留了几秒"))
            self.root.after(0, lambda: btn.configure(state="normal"))
            self.root.after(0, self.progress.stop)

        threading.Thread(target=run, daemon=True).start()

    def _toggle_keys(self):
        show = "" if self.show_keys.get() else "*"
        self.sk_entry.configure(show=show)
        self.ok_entry.configure(show=show)

    def _log(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _run(self):
        if self._running: return
        data_dir = self.qq_data_dir.get().strip()
        if not data_dir or not os.path.isdir(data_dir):
            messagebox.showerror("错误", f"QQ数据目录不存在:\n{data_dir}\n\n请手动填写正确的路径。")
            return

        import swap_perspective
        swap_perspective.QQ_DATA_DIR = data_dir

        for attr, name in [("source_qq","源账号"),("target_qq","目标对话"),("output_qq","输出账号"),("peer_qq","显示区域"),("right_qq","右侧显示")]:
            val = getattr(self, attr).get().strip()
            if not val:
                messagebox.showerror("错误", f"请填写{name}")
                return

        sk = self.source_key.get().strip()
        ok = self.output_key.get().strip()
        if not sk or not ok:
            messagebox.showerror("错误", "请填写密钥")
            return

        self._running = True
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress.start()
        self.status.configure(text="运行中...", foreground="blue")
        self._clear_log()

        args = {
            "source_qq": self.source_qq.get().strip(),
            "target_qq": self.target_qq.get().strip(),
            "output_qq": self.output_qq.get().strip(),
            "peer_qq": self.peer_qq.get().strip(),
            "right_qq": self.right_qq.get().strip(),
            "source_key": sk, "output_key": ok,
        }

        def run():
            import io
            old = sys.stdout
            sys.stdout = io.StringIO()
            try:
                deploy(**args)
                out = sys.stdout.getvalue()
                self.root.after(0, lambda: self._log(out))
                self.root.after(0, lambda: self.status.configure(text="完成", foreground="green"))
                self.root.after(0, lambda: messagebox.showinfo("完成", "互换完成！请打开QQ查看。"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"错误: {e}"))
                self.root.after(0, lambda: self.status.configure(text="失败", foreground="red"))
                self.root.after(0, lambda: messagebox.showerror("错误", str(e)))
            finally:
                sys.stdout = old
                self.root.after(0, self._done)

        threading.Thread(target=run, daemon=True).start()

    def _restore(self):
        output_qq = self.output_qq.get().strip()
        if not output_qq:
            messagebox.showerror("错误", "请先填写输出账号")
            return

        data_dir = self.qq_data_dir.get().strip()
        if not data_dir: return
        import swap_perspective
        swap_perspective.QQ_DATA_DIR = data_dir

        db = _db_path(output_qq)
        db_dir = os.path.dirname(db)
        backups = []
        if os.path.exists(db_dir):
            for f in os.listdir(db_dir):
                if "backup" in f and f.endswith(".db") or f.startswith("nt_msg.db.original"):
                    backups.append(os.path.join(db_dir, f))
        backups.sort(reverse=True)
        if not backups:
            messagebox.showerror("错误", "未找到备份文件")
            return

        latest = backups[0]
        ts = ""
        try:
            t = os.path.getmtime(latest)
            ts = f" ({datetime.fromtimestamp(t).strftime('%m-%d %H:%M')})"
        except: pass

        ok = messagebox.askokcancel("恢复数据库", f"将恢复：{os.path.basename(latest)}{ts}\n共 {len(backups)} 个备份。\n\n确认？")
        if not ok: return

        subprocess.run(["taskkill", "/F", "/IM", "QQ.exe"], capture_output=True)
        import time; time.sleep(1)

        for s in ("", "-wal", "-shm", "-first.material", "-last.material"):
            try:
                f = db + s
                if os.path.exists(f): os.remove(f)
            except Exception as e:
                pass

        try:
            shutil.copy(latest, db)
            self._log(f"[恢复] 已从 {os.path.basename(latest)} 恢复")
            self.status.configure(text="已恢复", foreground="green")
        except Exception as e:
            messagebox.showerror("错误", f"复制备份失败: {e}")
            return
        messagebox.showinfo("完成", "数据库已恢复")

    def _stop(self):
        self._log("用户停止")
        self._done()

    def _done(self):
        self._running = False
        self.run_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.progress.stop()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    agreed = messagebox.askokcancel(
        "⚠ 风险警告",
        "本工具通过修改本地QQ数据库实现聊天记录视角互换，\n属于对QQ客户端数据的非正常操作。\n\n"
        "使用本工具可能导致：\n  1. QQ账号被限制或冻结\n  2. 聊天记录丢失\n  3. 其他不可预知的后果\n\n"
        "本工具仅供学习研究，请勿用于非法用途。\n使用者自行承担一切风险及责任。\n\n"
        "点击「确定」表示已知晓并接受以上风险。\n点击「取消」退出程序。"
    )
    if not agreed:
        root.destroy()
        sys.exit(0)
    root.deiconify()
    App(root)
    root.mainloop()
