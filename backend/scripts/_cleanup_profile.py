# -*- coding: utf-8 -*-
"""临时清理脚本：移除 E2E 测试写入偏好档案的测试键（运行后即删）"""
import json

import requests

profile = requests.get("http://localhost:8000/api/profile", timeout=10).json()
content = profile["content"]
content.pop("max_single_position_pct", None)
resp = requests.put("http://localhost:8000/api/profile",
                    json={"content": content}, timeout=10).json()
print("cleaned, version:", resp["version"])
