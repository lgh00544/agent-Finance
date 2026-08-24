import sqlite3

con = sqlite3.connect(r"D:\self\data\dev.db")
con.row_factory = sqlite3.Row
for sid in (10,):
    rows = con.execute(
        "SELECT id, target_agent, target_kind, rule_type, rule_name, status, current_value, "
        "suggested_value, reason FROM agent_suggestion WHERE id = ?", (sid,)).fetchall()
    for r in rows:
        print(dict(r))
print("--- 全部 pending 建议概览 ---")
for r in con.execute(
        "SELECT id, target_agent, target_kind, rule_type, rule_name, status "
        "FROM agent_suggestion ORDER BY id"):
    print(dict(r))
con.close()
