"""修复 rag_engine.py 的 import traceback 缩进错误"""

path = r"E:\AICraft\src\core\rag_engine.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 删掉错误位置的 import traceback（方法体内的）
content = content.replace("\n            import traceback\n", "\n")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("OK - 已移除错误位置的 import traceback")
