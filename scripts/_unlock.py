# -*- coding: utf-8 -*-
"""清除 schemas.py 等目标文件的 Windows 只读属性（S_IWRITE），便于 Edit 工具改写"""
import os
import stat

targets = [
    r"D:\self\backend\app\agents\schemas.py",
    r"D:\self\backend\app\agents\market_intel.py",
    r"D:\self\backend\app\agents\common.py",
    r"D:\self\agent_prompts\market_intel_prompt.py",
    r"D:\self\streamlit\pages\12_市场研判.py",
]
for p in targets:
    try:
        st = os.stat(p)
        if not (st.st_mode & stat.S_IWRITE):
            os.chmod(p, st.st_mode | stat.S_IWRITE)
            print("CLEARED", p)
        else:
            print("OK-already-writable", p)
    except FileNotFoundError:
        print("MISSING", p)
    except Exception as e:
        print("ERR", p, e)
