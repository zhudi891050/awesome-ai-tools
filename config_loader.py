"""GEO系统配置加载器 — 统一配置入口 + ${VAR}环境变量替换"""
import os
import re
import yaml
from pathlib import Path


ROOT_DIR = Path(__file__).parent
CONFIG_PATH = ROOT_DIR / "config.yaml"

# 缓存：只加载一次
_config_cache = None


def _resolve_env_vars(value):
    """递归替换值中的 ${VAR} 为环境变量值"""
    if isinstance(value, str):
        # 匹配 ${VAR} 或 ${VAR:-default} 格式
        def replacer(match):
            var_expr = match.group(1)
            if ":-" in var_expr:
                var_name, default = var_expr.split(":-", 1)
                return os.environ.get(var_name.strip(), default.strip())
            return os.environ.get(var_expr, match.group(0))  # 未设置时保留原样

        return re.sub(r"\$\{([^}]+)\}", replacer, value)
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


def load_config(force_reload=False):
    """加载配置文件，自动替换 ${VAR} 环境变量
    
    用法:
        from config_loader import load_config
        config = load_config()
    """
    global _config_cache

    if _config_cache is not None and not force_reload:
        return _config_cache

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"配置文件不存在: {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    _config_cache = _resolve_env_vars(raw)
    return _config_cache


def get_config():
    """获取已缓存的配置（不重新加载）"""
    return _config_cache if _config_cache is not None else load_config()
