"""对比「本仓库读到的 Key」是否与另一项目一致：只打印长度与 SHA256 前缀，不输出密钥。"""
from __future__ import annotations

import hashlib

from app.services.llm.deepseek import _deepseek_api_key


def main() -> None:
    k = _deepseek_api_key()
    if not k:
        print("empty")
        return
    h = hashlib.sha256(k.encode("utf-8")).hexdigest()
    print("normalized_len:", len(k))
    print("sha256_prefix:", h[:16], "(与另一项目在相同脚本下应完全一致)")


if __name__ == "__main__":
    main()
