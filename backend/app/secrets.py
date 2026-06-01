"""
Secrets Manager — 密钥不落盘，按优先级加载。

加载顺序 (高→低):
  1. 环境变量               — Docker / K8s 注入，生产首选
  2. Docker Secret 文件     — /run/secrets/<key> (Swarm / K8s)
  3. .env 文件              — 仅开发环境，生产不应存在

用法:
    from app.secrets import secrets
    deepseek_key = secrets.get("DEEPSEEK_API_KEY")
"""

import os
import warnings
from typing import Dict, Optional, Set

# 项目根目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ENV_FILE = os.path.join(_PROJECT_ROOT, ".env")


def _parse_dotenv(path: str) -> Dict[str, str]:
    """Minimal .env parser — no dependency on python-dotenv."""
    result: Dict[str, str] = {}
    if not os.path.isfile(path):
        return result
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            result[key] = value
    return result


class SecretManager:
    """统一密钥入口。"""

    def __init__(self):
        self._env_cache: Optional[Dict[str, str]] = None
        self._prod = os.getenv("PRODUCTION", "").lower() in ("true", "1", "yes")
        self._warned: Set[str] = set()

    @property
    def _dotenv(self) -> Dict[str, str]:
        if self._env_cache is None:
            self._env_cache = _parse_dotenv(_ENV_FILE)
        return self._env_cache

    def get(self, key: str, default: str = "") -> str:
        """按优先级获取密钥值。"""

        # 1. 环境变量 (最高优先级)
        val = os.getenv(key)
        if val is not None:
            return val

        # 2. Docker Secret 文件
        secret_file = os.path.join("/run/secrets", key.lower())
        if os.path.isfile(secret_file):
            try:
                with open(secret_file, "r") as f:
                    return f.read().strip()
            except OSError:
                pass

        # 3. .env 文件 (仅非生产环境)
        if not self._prod:
            val = self._dotenv.get(key)
            if val:
                if key not in self._warned:
                    self._warned.add(key)
                    warnings.warn(
                        f"密钥 {key} 从 .env 文件读取，生产环境请改用环境变量或 Docker Secret。",
                        UserWarning,
                        stacklevel=2,
                    )
                return val

        return default

    def required(self, key: str) -> str:
        """获取必需的密钥，缺失则报错。"""
        val = self.get(key)
        if not val:
            raise RuntimeError(
                f"缺少必需的配置: {key}。请设置环境变量或 .env 文件。\n"
                f"  export {key}=<your-value>\n"
                f"  或参考 .env.example 创建 .env 文件"
            )
        return val

    @property
    def is_production(self) -> bool:
        return self._prod


# 全局单例
secrets = SecretManager()
