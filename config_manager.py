# -*- coding: utf-8 -*-
"""
配置管理模块 - 保存和读取用户配置
支持保存API Key等敏感信息到本地文件
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional

# 尝试导入 streamlit（用于云部署时读取 secrets）
try:
    import streamlit as st
    _has_streamlit = True
except ImportError:
    _has_streamlit = False

# 配置文件路径
CONFIG_DIR = Path(__file__).parent / "data"
CONFIG_DIR.mkdir(exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "user_config.json"

def save_config(provider: str, api_key: str, **kwargs) -> bool:
    """
    保存配置到本地文件
    
    Args:
        provider: AI服务商 (qwen/deepseek/ollama)
        api_key: API密钥
        **kwargs: 其他配置参数
        
    Returns:
        是否保存成功
    """
    try:
        # 读取现有配置
        config = load_config()
        
        # 更新配置
        config["provider"] = provider
        config["api_key"] = api_key
        
        # 保存其他参数
        for key, value in kwargs.items():
            config[key] = value
        
        # 写入文件
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        # 同时设置环境变量（当前会话有效）
        os.environ["AI_PROVIDER"] = provider
        if provider == "qwen":
            os.environ["QWEN_API_KEY"] = api_key
        elif provider == "deepseek":
            os.environ["DEEPSEEK_API_KEY"] = api_key
        
        return True
    except Exception as e:
        print(f"保存配置失败: {e}")
        return False

def load_config() -> Dict:
    """
    从本地文件加载配置
    
    Returns:
        配置字典
    """
    default_config = {
        "provider": "deepseek",
        "api_key": "",
        "base_url": "",
        "model": ""
    }
    
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 合并默认配置
                default_config.update(config)
    except Exception as e:
        print(f"加载配置失败: {e}")
    
    return default_config

def get_api_key(provider: str = None) -> str:
    """
    获取API Key（优先从 st.secrets(云部署)，其次环境变量，最后从配置文件）
    
    Args:
        provider: AI服务商
        
    Returns:
        API Key
    """
    # 最优先：从 st.secrets 读取（Streamlit Cloud 部署）
    if _has_streamlit:
        try:
            key_name = f"{provider.upper()}_API_KEY" if provider else "DEEPSEEK_API_KEY"
            secret_key = st.secrets.get(key_name, "")
            if secret_key:
                return secret_key
        except Exception:
            pass
    
    # 其次：从环境变量获取
    if provider == "qwen":
        key = os.getenv("QWEN_API_KEY", "")
        if key:
            return key
    elif provider == "deepseek":
        key = os.getenv("DEEPSEEK_API_KEY", "")
        if key:
            return key
    
    # 最后：从配置文件获取
    config = load_config()
    return config.get("api_key", "")

def get_provider() -> str:
    """
    获取当前配置的AI服务商
    
    Returns:
        服务商名称
    """
    # 优先从环境变量获取
    provider = os.getenv("AI_PROVIDER", "")
    if provider:
        return provider
    
    # 从配置文件获取
    config = load_config()
    return config.get("provider", "deepseek")

def clear_config():
    """清除所有配置"""
    try:
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
        
        # 清除环境变量
        for key in ["AI_PROVIDER", "QWEN_API_KEY", "DEEPSEEK_API_KEY", "OLLAMA_URL"]:
            if key in os.environ:
                del os.environ[key]
        
        return True
    except Exception as e:
        print(f"清除配置失败: {e}")
        return False

def test_config() -> Dict:
    """
    测试当前配置是否有效
    
    Returns:
        测试结果字典
    """
    config = load_config()
    provider = config.get("provider", "deepseek")
    api_key = config.get("api_key", "")
    
    if not api_key:
        return {
            "success": False,
            "message": "API Key 未配置",
            "provider": provider
        }
    
    # 尝试导入AI服务模块进行测试
    try:
        from ai_service import AIService
        
        ai = AIService(provider)
        result = ai.test_connection()
        return result
    except Exception as e:
        return {
            "success": False,
            "message": f"测试失败: {str(e)}",
            "provider": provider
        }

# 初始化时加载配置到环境变量
def init_config():
    """初始化配置 - 将配置文件中的配置加载到环境变量"""
    config = load_config()
    
    provider = config.get("provider", "deepseek")
    os.environ["AI_PROVIDER"] = provider
    
    api_key = config.get("api_key", "")
    if api_key:
        if provider == "qwen":
            os.environ["QWEN_API_KEY"] = api_key
        elif provider == "deepseek":
            os.environ["DEEPSEEK_API_KEY"] = api_key

# 模块加载时自动初始化
init_config()
