# -*- coding: utf-8 -*-
"""
AI服务模块 - 支持通义千问、DeepSeek、Ollama等多种AI服务
"""

import os
import json
import requests
from typing import Dict, List, Optional
from config import AIConfig

# 尝试导入 streamlit（用于云部署时读取 secrets）
try:
    import streamlit as st
    _has_streamlit = True
except ImportError:
    _has_streamlit = False

class AIService:
    """AI服务统一接口"""
    
    def __init__(self, provider: str = None, api_key: str = None):
        """
        初始化AI服务
        
        Args:
            provider: AI服务提供商，可选 'qwen', 'deepseek', 'ollama'
            api_key: API密钥（可选，优先使用此参数）
        """
        self.provider = provider or os.getenv("AI_PROVIDER", "deepseek")
        # 云部署优先读取 st.secrets 中的 provider
        if _has_streamlit:
            try:
                self.provider = st.secrets.get("AI_PROVIDER", self.provider)
            except Exception:
                pass
        self.config = AIConfig.get_current_config(self.provider)
        
        # API Key 优先级：直接传入 > st.secrets(云部署) > 配置文件 > 环境变量 > AIConfig默认值
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = ""
            # 1. 尝试从 st.secrets 读取（Streamlit Cloud 部署）
            if _has_streamlit:
                try:
                    key_name = f"{self.provider.upper()}_API_KEY"
                    self.api_key = st.secrets.get(key_name, "") or ""
                except Exception:
                    pass
            # 2. 尝试从配置管理模块读取（本地配置文件 user_config.json）
            if not self.api_key:
                try:
                    from config_manager import get_api_key
                    self.api_key = get_api_key(self.provider) or ""
                except Exception:
                    pass
            # 3. 最后从 AIConfig 默认值获取（环境变量）
            if not self.api_key:
                self.api_key = self.config.get("api_key", "")
        
        self.base_url = self.config["base_url"]
        self.model = self.config["model"]
        self.max_tokens = self.config.get("max_tokens", 2000)
        self.temperature = self.config.get("temperature", 0.7)
    
    def _call_api(self, messages: List[Dict], **kwargs) -> Dict:
        """
        调用AI API的通用方法
        
        Args:
            messages: 对话消息列表
            **kwargs: 其他参数
            
        Returns:
            AI响应字典
        """
        headers = {
            "Content-Type": "application/json"
        }
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature)
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            # 检查API返回的错误信息
            if "error" in result and "choices" not in result:
                error_msg = result.get("error", {})
                if isinstance(error_msg, dict):
                    error_msg = error_msg.get("message", str(error_msg))
                return {"error": str(error_msg), "choices": [{"message": {"content": ""}}]}
            return result
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "choices": [{"message": {"content": ""}}]}
    
    def chat(self, prompt: str, system_prompt: str = None) -> str:
        """
        发送对话请求
        
        Args:
            prompt: 用户输入
            system_prompt: 系统提示词
            
        Returns:
            AI回复内容
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        result = self._call_api(messages)
        
        if "error" in result:
            return f"请求失败: {result['error']}"
        
        return result.get("choices", [{}])[0].get("message", {}).get("content", "")
    
    def chat_with_image(self, prompt: str, image_base64: str = None) -> str:
        """
        发送带图片的对话请求（支持多模态模型）
        
        Args:
            prompt: 用户输入/问题
            image_base64: 图片的base64编码
            
        Returns:
            AI回复内容
        """
        messages = []
        
        # 构建图片消息
        if image_base64:
            content = [
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                }
            ]
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": prompt})
        
        # 构建payload - 使用支持视觉的模型
        headers = {
            "Content-Type": "application/json"
        }
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        # 视觉模型配置
        payload = {
            "model": "deepseek-chat",  # DeepSeek支持视觉
            "messages": messages,
            "max_tokens": 2000,
            "temperature": 0.7
        }
        
        # 如果是通义千问，使用其视觉模型
        if self.provider == "qwen":
            payload["model"] = "qwen-vl-plus"
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120  # 图片识别需要更长时间
            )
            response.raise_for_status()
            result = response.json()
            # 检查API返回的错误信息
            if "error" in result and "choices" not in result:
                error_msg = result.get("error", {})
                if isinstance(error_msg, dict):
                    error_msg = error_msg.get("message", str(error_msg))
                return f"请求失败: {str(error_msg)}"
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")
        except requests.exceptions.RequestException as e:
            return f"请求失败: {str(e)}"
    
    def diagnose_error(self, question: str, student_answer: str, correct_answer: str, 
                       knowledge_point: str, question_type: str = "单选题") -> Dict:
        """
        诊断学生错因
        
        Args:
            question: 题目内容
            student_answer: 学生答案
            correct_answer: 正确答案
            knowledge_point: 知识点
            question_type: 题目类型（单选题/填空题）
            
        Returns:
            诊断结果字典
        """
        system_prompt = f"""你是一位资深的高中化学教师，擅长分析学生的错题原因。

请分析以下化学题目（{question_type}）中学生的错误，并给出详细的诊断报告。

诊断维度（请严格从中选择最匹配的一项）：
1. concept_confusion（概念混淆）- 对化学概念的理解存在偏差或混淆
   例如：氧化剂和还原剂判断反了、电解质与非电解质混淆、同位素概念不清
2. calculation_error（计算失误）- 数学计算或单位换算出现错误
   例如：物质的量计算错误、气体摩尔体积应用错误、质量分数计算错误
3. careless_reading（审题不清）- 没有仔细阅读题目条件或要求
   例如：忽略"过量"条件、看错计量数、漏看"正确的是"还是"错误的是"
4. knowledge_gap（知识缺失）- 相关知识点掌握不足
   例如：常见方程式记忆不清、实验现象记忆不准确、物质性质不知道
5. reasoning_error（逻辑推理错误）- 解题思路或推理过程有误
   例如：反应顺序判断错误、产物推断错误、离子共存分析逻辑错误

请按以下JSON格式返回分析结果（必须是有效的JSON）：
{{
    "error_type": "具体属于哪种错误类型的中文名称",
    "error_type_code": "concept_confusion/calculation_error/careless_reading/knowledge_gap/reasoning_error（必须从这5个中选一个）",
    "diagnosis_detail": "详细分析学生的错误原因，说明为什么属于该错误类型",
    "knowledge_gaps": ["学生需要加强的知识点1", "知识点2"],
    "suggestion": "给学生的具体改进建议"
}}

请直接返回JSON，不要有其他内容。"""
        
        user_prompt = f"""题目类型：{question_type}

题目：{question}

正确答案：{correct_answer}

学生答案：{student_answer}

知识点：{knowledge_point}

请分析学生答案的错误原因，并严格从5种错误类型中选择最匹配的一项。"""
        
        result = self.chat(user_prompt, system_prompt)
        
        # 检查API调用是否失败
        if result.startswith("请求失败:"):
            return {
                "error_type": "AI服务异常",
                "error_type_code": "api_error",
                "diagnosis_detail": f"AI服务调用失败: {result}",
                "knowledge_gaps": [knowledge_point],
                "suggestion": "请检查AI服务配置和网络连接"
            }
        
        # 尝试解析JSON
        try:
            # 尝试提取JSON
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]
            
            diagnosis = json.loads(result.strip())
            return diagnosis
        except json.JSONDecodeError:
            # 如果解析失败，返回默认格式
            return {
                "error_type": "未分类",
                "error_type_code": "unknown",
                "diagnosis_detail": result,
                "knowledge_gaps": [knowledge_point],
                "suggestion": "建议复习相关知识点，多做练习"
            }
    
    def generate_practice_questions(self, target_knowledge: str, 
                                    error_type: str,
                                    difficulty: int = 1,
                                    count: int = 3,
                                    use_latex: bool = True) -> List[Dict]:
        """
        生成个性化练习题
        
        Args:
            target_knowledge: 目标知识点
            error_type: 错误类型（用于针对性出题）
            difficulty: 难度等级 1-5
            count: 生成题目数量
            use_latex: 是否使用LaTeX格式（化学式更准确）
            
        Returns:
            练习题列表
        """
        difficulty_desc = {
            1: "基础题，注重概念理解",
            2: "简单应用题",
            3: "中等难度，综合应用",
            4: "较难题，需要较强分析能力",
            5: "高难度竞赛级别"
        }
        
        latex_instruction = """
重要格式要求（必须严格遵守）：

一、化学式格式（使用LaTeX + mhchem）：
- 分子式：$\\ce{H2O}$、$\\ce{NaOH}$、$\\ce{Fe2O3}$、$\\ce{CO2}$
- 化学方程式（用等号=）：$\\ce{2Fe + O2 =[点燃] Fe2O3}$
- 加热条件用[\\triangle]：$\\ce{CuO + H2 =[\\triangle] Cu + H2O}$
- 催化剂条件：$\\ce{2H2O2 =[MnO2] 2H2O + O2 ^}$
- 离子方程式（用等号=）：$\\ce{Ba^{2+} + SO4^{2-} = BaSO4 v}$
- 注意：所有方程式（化学方程式和离子方程式）都使用等号"="连接，不使用箭头"->"
- 注意：加热条件必须使用[\\triangle]（LaTeX格式），绝对不能使用Unicode符号"△"
- 气体符号用^，沉淀符号用v：$\\ce{CaCO3 + 2HCl = CaCl2 + H2O + CO2 ^}$
- 离子符号：$\\ce{Na^+}$、$\\ce{SO4^{2-}}$、$\\ce{Cl^-}$
- 物质的量公式：$n = \\frac{m}{M}$（M为摩尔质量，单位g/mol）

二、电子式格式（使用纯文本描述）：
- 电子式用纯文本描述更清晰，例如：
  氯化钠电子式：Na⁺[:Cl:]⁻（Cl⁻加方括号，标电荷）
  水分子电子式：H:Ö:H（Ö表示氧原子，氧有2对孤对电子）
  氯化氢电子式：H:Cl:（Cl有3对孤对电子）
  二氧化碳电子式：Ö::C::Ö（C和O之间两对共用电子对）
- 重要规则：
  1. 阴离子必须用方括号括起来并标电荷，如 [:Cl:]⁻、[:O:]²⁻
  2. 阳离子直接写符号，如 Na⁺、Mg²⁺
  3. 共用电子对用冒号(:)表示，每对共用电子对写一个冒号
  4. 孤对电子可以用(..)或文字说明
  5. 不要使用LaTeX的\\ddot命令，它不被mhchem支持

三、结构式格式（使用LaTeX）：
- 氮气结构式（三键）：$\\ce{N#N}$
- 乙烯结构式（双键）：$\\ce{H2C=CH2}$
- 乙炔结构式（三键）：$\\ce{HC#CH}$
- 注意：单键用-表示，双键用=表示，三键用#表示

四、原子/离子结构示意图（使用结构化标签，不要用LaTeX或文字画图）：
- 必须使用以下格式：[ION_DATA: 离子符号, 核电荷数, [每层电子数]]
- 示例：
  镁离子：[ION_DATA: Mg2+, 12, [2, 8]]
  氯原子：[ION_DATA: Cl, 17, [2, 8, 7]]
  钠离子：[ION_DATA: Na+, 11, [2, 8]]
  氧离子：[ION_DATA: O2-, 8, [2, 6]]
- 注意：绝对不要尝试用LaTeX、文字符号或特殊字符画原子结构图
- 只输出[ION_DATA: ...]标签，系统会自动渲染为标准图形

五、特别注意：
- 氮气分子中N≡N是三键，不是单键N—N
- 水分子中氧原子有2对孤对电子
- NaCl是离子化合物，电子式中Cl⁻要加方括号
- 离子化合物电子式：阳离子写符号（如Na⁺），阴离子加方括号（如[:Cl:]⁻）
- 共价化合物电子式：原子之间用冒号表示共用电子对，不加方括号
- 化学方程式必须配平（等号两边原子种类和数目相等）
""" if use_latex else ""
        
        system_prompt = f"""你是一位专业的高中化学教师，擅长设计针对性练习题。

请根据学生的薄弱知识点，设计变式练习题。

要求：
1. 题目要针对学生的错误类型进行设计
2. 难度要循序渐进
3. 每道题都要有详细的解析
4. 题目要紧扣高一化学教学大纲
{latex_instruction}
请按以下JSON格式返回（必须是有效的JSON）：
{{
    "questions": [
        {{
            "question_text": "题目内容（化学式用LaTeX，不要使用任何HTML标签如<b><span>等）",
            "options": ["A选项", "B选项", "C选项", "D选项"],
            "answer": "正确答案（仅写A/B/C/D）",
            "explanation": "详细解析（化学式用LaTeX，不要使用HTML标签）",
            "difficulty": 1-5,
            "knowledge_point": "所属知识点"
        }}
    ]
}}

重要提醒：
- 题目内容和选项中绝对不要使用任何HTML标签（如<b>、<span>、<br>等）
- 化学式全部使用LaTeX格式：$\\ce{{...}}$
- 选项文本直接写内容，不要加"A. "前缀，系统会自动添加
- 正确答案只写字母（A/B/C/D），不要写完整内容

请直接返回JSON，不要有其他内容。"""
        
        user_prompt = f"""目标知识点：{target_knowledge}

学生常见错误类型：{error_type}

题目难度：{difficulty_desc.get(difficulty, "中等难度")}

请生成{count}道变式练习题。"""
        
        result = self.chat(user_prompt, system_prompt)
        
        # 检查API调用是否失败
        if result.startswith("请求失败:"):
            print(f"[AI Service] API调用失败: {result}")
            return []
        
        # 尝试解析JSON
        try:
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]
            
            data = json.loads(result.strip())
            questions = data.get("questions", [])
            # 给每道题标注knowledge_point
            for q in questions:
                if 'knowledge_point' not in q:
                    q['knowledge_point'] = target_knowledge
            return questions
        except (json.JSONDecodeError, IndexError) as e:
            print(f"[AI Service] JSON解析失败: {e}, 原始返回: {result[:200]}")
            return []
    
    def generate_knowledge_report(self, knowledge_stats: Dict) -> str:
        """
        生成知识点掌握情况报告
        
        Args:
            knowledge_stats: 知识点统计数据
            
        Returns:
            分析报告文本
        """
        system_prompt = """你是一位专业的高中化学教研员，擅长分析学生的学习数据。

请根据提供的知识点统计数据，生成一份详细的学习分析报告。

报告要求：
1. 指出学生的优势知识点
2. 指出需要加强的薄弱知识点
3. 提供针对性的学习建议
4. 语气要鼓励性，给学生信心

请用中文回答，条理清晰。"""
        
        stats_text = json.dumps(knowledge_stats, ensure_ascii=False, indent=2)
        user_prompt = f"请分析以下知识点掌握情况：\n{stats_text}"
        
        return self.chat(user_prompt, system_prompt)
    
    def parse_homework_image(self, image_path: str = None, image_data: bytes = None) -> List[Dict]:
        """
        从作业图片中解析题目和学生答案
        
        Args:
            image_path: 图片路径
            image_data: 图片二进制数据
            
        Returns:
            解析出的题目列表
        """
        system_prompt = """你是一位专业的高中化学教师，擅长识别和解析化学题目。

请从上传的作业图片中识别题目和学生答案。

识别要求：
1. 准确识别化学方程式、符号
2. 识别学生的书写内容
3. 判断学生答案是否正确
4. 如果是选择题，识别学生选择的选项

请按以下JSON格式返回（必须是有效的JSON）：
{
    "questions": [
        {
            "question_text": "识别到的题目内容",
            "student_answer": "学生的答案",
            "is_parsed": true/false,
            "confidence": 0.0-1.0
        }
    ]
}

如果图片质量不好或无法识别，请返回空列表。

请直接返回JSON，不要有其他内容。"""
        
        # 注意：实际使用时需要上传图片，这里简化处理
        return []
    
    def test_connection(self) -> Dict:
        """
        测试AI服务连接
        
        Returns:
            测试结果
        """
        try:
            response = self.chat("你好，请回复'连接成功'四个字。")
            # 判断是否请求失败
            if response.startswith("请求失败:"):
                return {"success": False, "message": f"{self.provider} 服务连接失败: {response}"}
            # 判断是否包含"成功"且不包含"失败"
            if "成功" in response and "失败" not in response:
                return {"success": True, "message": f"{self.provider} 服务连接正常"}
            else:
                return {"success": False, "message": f"{self.provider} 服务响应异常: {response}"}
        except Exception as e:
            return {"success": False, "message": f"{self.provider} 服务连接失败: {str(e)}"}


# 全局AI服务实例（延迟初始化）
_ai_service = None

def get_ai_service(provider: str = None) -> AIService:
    """获取AI服务实例"""
    global _ai_service
    if _ai_service is None or (provider and _ai_service.provider != provider):
        _ai_service = AIService(provider)
    return _ai_service
