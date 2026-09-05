"""确定性导出 FastAPI OpenAPI 契约，并输出 SHA-256 摘要。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app  # noqa: E402：先将项目根目录加入导入路径


OUTPUT_PATH = (
    PROJECT_ROOT / "docs" / "contracts" / f"openapi-v{app.version}.json"
)


def serialize_openapi() -> str:
    """使用固定键顺序和缩进生成便于审查的契约文本。"""

    return json.dumps(app.openapi(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def main() -> None:
    """覆盖已审查的契约基线；调用方应同时运行契约测试。"""

    content = serialize_openapi()
    encoded = content.encode("utf-8")
    # 写入字节可避免 Windows 自动把 LF 转换为 CRLF，保证跨平台摘要一致。
    OUTPUT_PATH.write_bytes(encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    print(f"OpenAPI baseline: {OUTPUT_PATH}")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
