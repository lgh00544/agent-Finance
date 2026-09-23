raw = open(r"D:\self\.pytest_tmp_out.txt", "rb").read()
txt = raw.decode("utf-16", "replace") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8", "replace")
lines = txt.splitlines()
print("lines=%d" % len(lines))
for l in lines[:45]:
    print(l[:240])