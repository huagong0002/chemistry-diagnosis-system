# -*- coding: utf-8 -*-
"""
示例数据生成器 - 用于演示和测试系统功能
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from database import db
from models import Student, Question, StudentAnswer, ErrorDiagnosis
from config import CHEMISTRY_KNOWLEDGE_POINTS

def generate_sample_data():
    """生成示例数据"""
    
    print("正在生成示例数据...")
    
    # 1. 添加示例班级
    print("添加示例班级...")
    db.add_class("高一(1)班", "高一")
    db.add_class("高一(2)班", "高一")
    
    # 2. 添加示例学生
    print("添加示例学生...")
    students = [
        Student(name="张三", student_id="2026001", class_name="高一(1)班", grade="高一"),
        Student(name="李四", student_id="2026002", class_name="高一(1)班", grade="高一"),
        Student(name="王五", student_id="2026003", class_name="高一(1)班", grade="高一"),
        Student(name="赵六", student_id="2026004", class_name="高一(2)班", grade="高一"),
        Student(name="钱七", student_id="2026005", class_name="高一(2)班", grade="高一"),
    ]
    
    student_ids = []
    for s in students:
        try:
            sid = db.add_student(s)
            student_ids.append(sid)
            print(f"  添加学生: {s.name}")
        except Exception as e:
            print(f"  添加学生失败: {s.name} - {e}")
    
    # 3. 添加示例题目
    print("添加示例题目...")
    questions = [
        Question(
            question_text="配平下列化学方程式：Fe + O₂ → Fe₂O₃",
            question_type="计算题",
            knowledge_point="氧化还原反应",
            difficulty=2,
            correct_answer="4Fe + 3O₂ → 2Fe₂O₃",
            source="人教版必修一 第二章"
        ),
        Question(
            question_text="判断下列物质属于电解质还是非电解质：NaCl、HCl、CO₂、酒精",
            question_type="选择题",
            knowledge_point="离子反应",
            difficulty=2,
            correct_answer="NaCl是电解质、HCl是电解质、CO₂是非电解质、酒精是非电解质",
            source="人教版必修一 第三章"
        ),
        Question(
            question_text="计算：0.5 mol O₂ 的质量是多少？",
            question_type="计算题",
            knowledge_point="物质的量",
            difficulty=1,
            correct_answer="16g",
            source="人教版必修一 第一章"
        ),
        Question(
            question_text="写出钠与水反应的化学方程式",
            question_type="简答题",
            knowledge_point="金属及其化合物",
            difficulty=2,
            correct_answer="2Na + 2H₂O → 2NaOH + H₂↑",
            source="人教版必修一 第三章"
        ),
        Question(
            question_text="判断：Cl₂能与NaOH溶液反应生成NaCl、NaClO和H₂O",
            question_type="判断题",
            knowledge_point="非金属及其化合物",
            difficulty=3,
            correct_answer="正确",
            source="人教版必修一 第四章"
        ),
    ]
    
    question_ids = []
    for q in questions:
        try:
            qid = db.add_question(q)
            question_ids.append(qid)
            print(f"  添加题目: {q.question_text[:30]}...")
        except Exception as e:
            print(f"  添加题目失败 - {e}")
    
    # 4. 添加示例答题记录和诊断
    print("添加示例诊断记录...")
    diagnoses = [
        {
            "student_idx": 0,
            "question_idx": 0,
            "student_answer": "2Fe + 3O₂ → 2Fe₂O₃",
            "error_type": "calculation_error",
            "error_type_name": "计算失误",
            "diagnosis_detail": "学生没有正确计算铁原子的最小公倍数。铁原子在左边只有1个，右边有2个，需要乘以2；氧原子左边有2个，右边有3个，需要找2和3的最小公倍数6。正确的配平是4Fe + 3O₂ → 2Fe₂O₃。",
            "knowledge_gaps": ["氧化还原反应配平方法", "最小公倍数法"],
            "suggestion": "建议复习最小公倍数法配平氧化还原方程式，多做相关练习题巩固。"
        },
        {
            "student_idx": 1,
            "question_idx": 1,
            "student_answer": "NaCl是电解质、HCl是非电解质",
            "error_type": "concept_confusion",
            "error_type_name": "概念混淆",
            "diagnosis_detail": "学生混淆了电解质和非电解质的概念。HCl在水溶液中能够导电（虽然它是共价化合物，但在水中完全电离），因此是电解质。只有在水中或熔融状态下都不能导电的化合物才是非电解质。",
            "knowledge_gaps": ["电解质的定义", "电解质与非电解质的区别"],
            "suggestion": "建议重新理解电解质的定义：'在水溶液中或熔融状态下能导电的化合物'。"
        },
        {
            "student_idx": 2,
            "question_idx": 2,
            "student_answer": "32g",
            "error_type": "calculation_error",
            "error_type_name": "计算失误",
            "diagnosis_detail": "学生的计算过程中可能混淆了摩尔质量和质量的关系。O₂的摩尔质量是32g/mol，0.5 mol O₂的质量应该是：m = n × M = 0.5mol × 32g/mol = 16g。",
            "knowledge_gaps": ["摩尔质量的概念", "质量与物质的量的关系"],
            "suggestion": "建议复习m = n × M这个公式，明确各个物理量的单位。"
        },
        {
            "student_idx": 0,
            "question_idx": 3,
            "student_answer": "Na + H₂O → NaOH + H₂",
            "error_type": "calculation_error",
            "error_type_name": "计算失误",
            "diagnosis_detail": "学生没有配平化学方程式。左边钠原子1个，右边2个；左边氢原子1个，右边3个。需要配平钠原子（×2）。",
            "knowledge_gaps": ["化学方程式配平"],
            "suggestion": "注意检查方程式两边各原子的数目是否相等。"
        },
        {
            "student_idx": 3,
            "question_idx": 4,
            "student_answer": "错误",
            "error_type": "knowledge_gap",
            "error_type_name": "知识缺失",
            "diagnosis_detail": "学生可能对氯气与氢氧化钠溶液的反应掌握不清。这个反应是正确的，化学方程式为：Cl₂ + 2NaOH → NaCl + NaClO + H₂O。",
            "knowledge_gaps": ["氯气的化学性质", "氯气与碱反应"],
            "suggestion": "建议复习氯气与不同物质反应的产物特点。"
        },
    ]
    
    for d in diagnoses:
        try:
            diagnosis = ErrorDiagnosis(
                question_id=question_ids[d["question_idx"]],
                student_id=student_ids[d["student_idx"]],
                error_type=d["error_type"],
                error_type_name=d["error_type_name"],
                diagnosis_detail=d["diagnosis_detail"],
                knowledge_gaps=d["knowledge_gaps"],
                suggestion=d["suggestion"]
            )
            db.add_diagnosis(diagnosis)
            print(f"  添加诊断: 学生{student_ids[d['student_idx']]} - {d['error_type_name']}")
        except Exception as e:
            print(f"  添加诊断失败 - {e}")
    
    print("\n✅ 示例数据生成完成！")
    print(f"   - 班级: 2个")
    print(f"   - 学生: {len(student_ids)}人")
    print(f"   - 题目: {len(question_ids)}道")
    print(f"   - 诊断记录: {len(diagnoses)}条")

def reset_database():
    """重置数据库（谨慎使用）"""
    import shutil
    from config import DATABASE_PATH
    
    if os.path.exists(DATABASE_PATH):
        backup_path = str(DATABASE_PATH) + ".backup"
        shutil.copy(DATABASE_PATH, backup_path)
        print(f"已备份数据库到: {backup_path}")
    
    # 删除并重建
    if os.path.exists(DATABASE_PATH):
        os.remove(DATABASE_PATH)
    
    # 重新初始化
    from database import Database
    db = Database()
    
    print("数据库已重置！")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="示例数据生成工具")
    parser.add_argument("--reset", action="store_true", help="重置数据库")
    
    args = parser.parse_args()
    
    if args.reset:
        confirm = input("确定要重置数据库吗？这将清空所有数据！(y/n): ")
        if confirm.lower() == 'y':
            reset_database()
            generate_sample_data()
        else:
            print("已取消")
    else:
        generate_sample_data()
