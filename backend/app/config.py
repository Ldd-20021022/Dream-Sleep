"""
应用配置 — 非敏感字段直接用 pydantic-settings，
敏感字段 (密钥) 通过 SecretManager 加载 (env > Docker secret > .env)。
"""

import os

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

# 项目根目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Settings(BaseSettings):
    # ========== 数据库 ==========
    DATABASE_URL: str = "mysql+pymysql://root:CHANGE-ME@localhost:3306/sleep_manager"

    # ========== JWT ==========
    SECRET_KEY: str = "change-this-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080
    ALGORITHM: str = "HS256"

    # ========== AI ==========
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    # ========== 微信 ==========
    WECHAT_APPID: str = ""
    WECHAT_SECRET: str = ""

    # ========== 运行模式 ==========
    PRODUCTION: bool = False

    class Config:
        env_file = os.path.join(_PROJECT_ROOT, ".env")
        extra = "ignore"


def _apply_secrets(s: Settings) -> Settings:
    """用 SecretManager 覆盖敏感字段的默认值。

    SecretManager 优先级: 环境变量 > Docker Secret 文件 > .env 文件。
    pydantic-settings 已经读了环境变量和 .env，这里补上 Docker Secret 这一层。
    """
    from app.secrets import secrets as _sec

    # 这些字段如果仍是默认值，尝试从 SecretManager 获取
    _sensitive = {
        "DATABASE_URL": "mysql+pymysql://root:CHANGE-ME@localhost:3306/sleep_manager",
        "SECRET_KEY": "change-this-in-production",
        "DEEPSEEK_API_KEY": "",
        "WECHAT_SECRET": "",
    }

    for field, default_val in _sensitive.items():
        current = getattr(s, field)
        # 如果当前值等于 Settings 类里写的默认值 (即未被 env_var / .env 覆盖)
        if current == default_val or not current:
            from_secret = _sec.get(field)
            if from_secret:
                object.__setattr__(s, field, from_secret)

    return s


settings = _apply_secrets(Settings())

# 生产环境安全警告
if settings.SECRET_KEY == "change-this-in-production":
    import warnings
    warnings.warn("SECRET_KEY 使用默认值！请设置环境变量 SECRET_KEY 或创建 .env 文件。")
