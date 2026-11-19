# app_paths.py
# -*- coding: utf-8 -*-
"""
程序路径与用户数据目录解耦模块：
- get_bundle_root(): 只读打包资源根目录（PyInstaller 解压目录或开发源码根目录）
- get_data_dir(): 用户可写数据目录（优先读取环境变量 NOVELFLOW_DATA_DIR；升级软件版本 100% 保留配置与稿件）
- get_books_root(): 小说项目默认存放目录（支持用户在软件内自选如 D:\\MyNovels）
"""

import json
import os
import shutil
import sys


def get_bundle_root() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.abspath(sys._MEIPASS)
    return os.path.dirname(os.path.abspath(__file__))


def get_data_dir() -> str:
    env_dir = (os.environ.get("NOVELFLOW_DATA_DIR") or "").strip()
    if env_dir:
        path = os.path.abspath(env_dir)
        os.makedirs(path, exist_ok=True)
        return path
    return os.path.dirname(os.path.abspath(__file__))


def get_data_file(filename: str) -> str:
    return os.path.join(get_data_dir(), filename)


def get_data_subdir(subdir: str, seed_from_bundle: bool = True) -> str:
    target = os.path.join(get_data_dir(), subdir)
    os.makedirs(target, exist_ok=True)
    if seed_from_bundle:
        bundled = os.path.join(get_bundle_root(), subdir)
        if os.path.isdir(bundled) and os.path.abspath(bundled) != os.path.abspath(target):
            try:
                if not os.listdir(target):
                    for item in os.listdir(bundled):
                        src = os.path.join(bundled, item)
                        dst = os.path.join(target, item)
                        if os.path.isfile(src) and not os.path.exists(dst):
                            shutil.copy2(src, dst)
            except Exception:
                pass
    return target


def get_books_root() -> str:
    cfg_file = get_data_file("config.json")
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                custom = (data.get("books_root") or "").strip()
                if custom:
                    os.makedirs(custom, exist_ok=True)
                    return custom
        except Exception:
            pass
    default_dir = os.path.join(get_data_dir(), "output")
    os.makedirs(default_dir, exist_ok=True)
    return default_dir


def set_books_root(new_root: str) -> str:
    clean = os.path.abspath(new_root.strip())
    os.makedirs(clean, exist_ok=True)
    cfg_file = get_data_file("config.json")
    data = {}
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
        except Exception:
            data = {}
    data["books_root"] = clean
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return clean
