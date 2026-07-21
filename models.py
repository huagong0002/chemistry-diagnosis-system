# -*- coding: utf-8 -*-
"""
数据模型 - 定义系统使用的数据结构
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
from datetime import datetime
import json

@dataclass
class Student:
    """学生信息"""
    id: Optional[int] = None
    name: str = ""
    student_id: str = ""  # 学号
    class_name: str = ""  # 班级
    grade: str = "高一"
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@dataclass
class Question:
    """题目信息"""
    id: Optional[int] = None
    question_text: str = ""  # 题目内容
    question_type: str = ""   # 题目类型：选择/填空/简答/计算
    knowledge_point: str = "" # 所属知识点
    difficulty: int = 1       # 难度等级 1-5
    correct_answer: str = ""   # 正确答案
    source: str = ""          # 来源（如：人教版必修一第三章）
    
    def to_dict(self):
        return asdict(self)

@dataclass
class StudentAnswer:
    """学生答题记录"""
    id: Optional[int] = None
    student_id: int = 0
    question_id: int = 0
    student_answer: str = ""  # 学生答案
    is_correct: bool = False
    submitted_at: str = ""
    
    def __post_init__(self):
        if not self.submitted_at:
            self.submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@dataclass
class ErrorDiagnosis:
    """错因诊断结果"""
    question_id: int = 0
    student_id: int = 0
    error_type: str = ""           # 错误类型
    error_type_name: str = ""      # 错误类型名称
    diagnosis_detail: str = ""      # 详细诊断
    knowledge_gaps: List[str] = field(default_factory=list)  # 知识薄弱点
    suggestion: str = ""           # 改进建议
    diagnosed_at: str = ""
    
    def __post_init__(self):
        if not self.diagnosed_at:
            self.diagnosed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def to_dict(self):
        return asdict(self)

@dataclass
class PersonalizedPractice:
    """个性化练习"""
    id: Optional[int] = None
    student_id: int = 0
    target_knowledge: str = ""     # 目标知识点
    practice_questions: List[Dict] = field(default_factory=list)  # 练习题列表
    difficulty_level: int = 1       # 练习难度
    is_completed: bool = False
    completion_rate: float = 0.0   # 完成率
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@dataclass
class DiagnosisReport:
    """诊断报告"""
    student_id: int = 0
    student_name: str = ""
    class_name: str = ""
    total_questions: int = 0
    correct_count: int = 0
    error_count: int = 0
    accuracy_rate: float = 0.0
    error_distribution: Dict[str, int] = field(default_factory=dict)  # 错误类型分布
    knowledge_weakness: Dict[str, float] = field(default_factory=dict)  # 知识点薄弱度
    recommendations: List[str] = field(default_factory=list)  # 改进建议
    generated_at: str = ""
    
    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self.total_questions > 0:
            self.accuracy_rate = round(self.correct_count / self.total_questions * 100, 1)
    
    def to_dict(self):
        return asdict(self)

@dataclass
class Homework:
    """作业记录"""
    id: Optional[int] = None
    title: str = ""
    description: str = ""
    class_name: str = ""
    subject: str = "化学"
    teacher_id: int = 0
    questions: List[Dict] = field(default_factory=list)  # 题目列表
    submission_count: int = 0
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ========== API响应模型 ==========

@dataclass
class APIResponse:
    """通用API响应"""
    success: bool
    message: str
    data: Optional[Dict] = None
    error: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)

@dataclass
class OCRResult:
    """OCR识别结果"""
    text: str
    confidence: float
    boxes: List[Dict] = field(default_factory=list)  # 文字区域坐标
    
    def to_dict(self):
        return asdict(self)
