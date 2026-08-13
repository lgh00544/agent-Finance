# -*- coding: utf-8 -*-
"""诊断 agents 目录多个文件的写入锁定状态"""
import os

paths = [
    r"D:\self\backend\app\agents\schemas.py",
    r"D:\self\backend\app\agents\market_intel.py",
    r"D:\self\backend\app\agents\common.py",
    r"D:\self\agent_prompts\market_intel_prompt.py",
    r"D:\self\streamlit\pages\12_市场研判.py",
]
for p in paths:
    try:
        with open(p, "a", encoding="utf-8") as f:
            pass
        print("APPEND-OK", os.path.basename(p))
    except Exception as e:
        print("APPEND-ERR", os.path.basename(p), type(e).__name__, e)
