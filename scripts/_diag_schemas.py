# -*- coding: utf-8 -*-
"""测试 schemas.py 是否可被 python 直接写入（诊断 EPERM）"""
p = r"D:\self\backend\app\agents\schemas.py"
try:
    with open(p, "a", encoding="utf-8") as f:
        f.write("")
    print("APPEND-OK")
except Exception as e:
    print("APPEND-ERR", type(e).__name__, e)
try:
    with open(p, "r+", encoding="utf-8") as f:
        f.seek(0)
        head = f.read(50)
    print("READWRITE-OK", repr(head[:30]))
except Exception as e:
    print("READWRITE-ERR", type(e).__name__, e)
