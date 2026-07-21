# -*- coding: utf-8 -*-
"""
配置文件 - 集中管理所有可配置参数
"""

import os
from pathlib import Path

# ========== 项目路径配置 ==========
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# ========== 数据库配置 ==========
DATABASE_PATH = DATA_DIR / "chemistry_diagnosis.db"

# ========== AI服务配置 ==========
# 支持多种AI服务，优先使用环境变量配置

class AIConfig:
    """AI服务配置"""
    
    # 通义千问（阿里云）- 推荐国内使用
    QWEN_CONFIG = {
        "provider": "qwen",
        "api_key": os.getenv("QWEN_API_KEY", ""),
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "max_tokens": 2000,
        "temperature": 0.7
    }
    
    # DeepSeek - 性价比高
    DEEPSEEK_CONFIG = {
        "provider": "deepseek",
        "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "max_tokens": 2000,
        "temperature": 0.7
    }
    
    # Ollama（本地部署）- 完全免费
    OLLAMA_CONFIG = {
        "provider": "ollama",
        "base_url": os.getenv("OLLAMA_URL", "http://localhost:11434/v1"),
        "model": os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        "max_tokens": 2000,
        "temperature": 0.7
    }
    
    # 当前使用的配置（可切换）
    @classmethod
    def get_current_config(cls, provider=None):
        """获取当前AI配置"""
        if provider is None:
            provider = os.getenv("AI_PROVIDER", "qwen")
        
        configs = {
            "qwen": cls.QWEN_CONFIG,
            "deepseek": cls.DEEPSEEK_CONFIG,
            "ollama": cls.OLLAMA_CONFIG
        }
        
        return configs.get(provider, cls.QWEN_CONFIG)

# ========== 高一化学知识点库 ==========
# 默认知识点库（内置）
DEFAULT_KNOWLEDGE_POINTS = {
    "氧化还原反应": {
        "code": "YHYY",
        "keywords": ["氧化反应", "还原反应", "氧化剂", "还原剂", "电子转移", "化合价"],
        "common_errors": [
            "氧化剂和还原剂判断错误",
            "电子转移数目计算错误",
            "氧化还原反应方程式配平错误"
        ]
    },
    "离子反应": {
        "code": "LYFY",
        "keywords": ["电解质", "非电解质", "离子方程式", "离子共存", "拆写"],
        "common_errors": [
            "不会判断电解质",
            "离子方程式书写不符合事实",
            "离子共存判断错误"
        ]
    },
    "物质的量": {
        "code": "WDDL",
        "keywords": ["摩尔", "摩尔质量", "气体摩尔体积", "物质的量浓度", "阿伏伽德罗常数"],
        "common_errors": [
            "公式混淆",
            "单位换算错误",
            "概念理解不到位"
        ]
    },
    "元素周期律": {
        "code": "YSZQX",
        "keywords": ["原子序数", "核外电子排布", "周期", "族", "金属性", "非金属性"],
        "common_errors": [
            "原子结构与性质关系不清",
            "元素推断错误",
            "同周期同主族递变规律混淆"
        ]
    },
    "金属及其化合物": {
        "code": "JSJWZHW",
        "keywords": ["钠", "铝", "铁", "氧化物", "氢氧化物", "盐", "焰色反应"],
        "common_errors": [
            "方程式记忆不清",
            "实验现象描述不准确",
            "转化关系混乱"
        ]
    },
    "非金属及其化合物": {
        "code": "FJSJWZHW",
        "keywords": ["硅", "氯", "硫", "氮", "氧化物", "氢化物", "酸"],
        "common_errors": [
            "氯气性质记忆混乱",
            "硫的化合物转化关系不清",
            "氨气制备和性质混淆"
        ]
    }
}

# 动态获取知识点库（支持自定义）
def get_knowledge_points():
    """获取知识点库，优先从文件加载自定义配置"""
    try:
        from knowledge_manager import load_knowledge_points
        return load_knowledge_points()
    except ImportError:
        return DEFAULT_KNOWLEDGE_POINTS.copy()

# 兼容旧代码的变量
CHEMISTRY_KNOWLEDGE_POINTS = get_knowledge_points()

# ========== 错因分类定义 ==========
ERROR_TYPES = {
    "concept_confusion": {
        "name": "概念混淆",
        "description": "对化学概念的理解存在偏差或混淆",
        "examples": ["氧化剂和还原剂判断", "电解质与非电解质混淆"]
    },
    "calculation_error": {
        "name": "计算失误",
        "description": "数学计算或单位换算出现错误",
        "examples": ["物质的量计算错误", "气体摩尔体积应用错误"]
    },
    "careless_reading": {
        "name": "审题不清",
        "description": "没有仔细阅读题目条件或要求",
        "examples": ["忽略温度压强条件", "看错计量数"]
    },
    "knowledge_gap": {
        "name": "知识缺失",
        "description": "相关知识点掌握不足",
        "examples": ["常见方程式记忆不清", "实验现象记忆不准确"]
    },
    "reasoning_error": {
        "name": "逻辑推理错误",
        "description": "解题思路或推理过程有误",
        "examples": ["反应顺序判断错误", "产物推断错误"]
    }
}

# ========== UI配置 ==========
STREAMLIT_CONFIG = {
    "page_title": "高中化学错题智能诊断与个性化练习系统",
    "page_icon": "🧪",
    "layout": "wide",
    "menu_items": {
        "About": "## 高中化学错题智能诊断与个性化练习系统\n\n基于AI技术的高中化学错题诊断与个性化练习平台，智能分析薄弱点，精准推送练习题，助力高效学习。",
        "Get Help": None,
        "Report a Bug": None
    }
}
