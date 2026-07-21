# -*- coding: utf-8 -*-
"""
数据库管理模块 - 使用SQLite存储所有数据
"""

import sqlite3
from pathlib import Path
from typing import List, Optional, Dict
from contextlib import contextmanager
import json

from config import DATABASE_PATH
from models import Student, Question, StudentAnswer, ErrorDiagnosis, PersonalizedPractice, Homework

class Database:
    """数据库管理类"""
    
    def __init__(self, db_path: str = str(DATABASE_PATH)):
        self.db_path = db_path
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_database(self):
        """初始化数据库表结构"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 学生表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    student_id TEXT UNIQUE,
                    class_name TEXT,
                    grade TEXT DEFAULT '高一',
                    created_at TEXT
                )
            ''')
            
            # 题目表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_text TEXT NOT NULL,
                    question_type TEXT,
                    knowledge_point TEXT,
                    difficulty INTEGER DEFAULT 1,
                    correct_answer TEXT,
                    source TEXT
                )
            ''')
            
            # 学生答题记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS student_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    question_id INTEGER,
                    student_answer TEXT,
                    is_correct INTEGER DEFAULT 0,
                    submitted_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(id),
                    FOREIGN KEY (question_id) REFERENCES questions(id)
                )
            ''')
            
            # 错因诊断表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS error_diagnoses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER,
                    student_id INTEGER,
                    error_type TEXT,
                    error_type_name TEXT,
                    diagnosis_detail TEXT,
                    knowledge_gaps TEXT,
                    suggestion TEXT,
                    diagnosed_at TEXT,
                    FOREIGN KEY (question_id) REFERENCES questions(id),
                    FOREIGN KEY (student_id) REFERENCES students(id)
                )
            ''')
            
            # 个性化练习表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS personalized_practices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    target_knowledge TEXT,
                    practice_questions TEXT,
                    difficulty_level INTEGER DEFAULT 1,
                    is_completed INTEGER DEFAULT 0,
                    completion_rate REAL DEFAULT 0.0,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(id)
                )
            ''')
            
            # 作业表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS homeworks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    class_name TEXT,
                    subject TEXT DEFAULT '化学',
                    teacher_id INTEGER,
                    questions TEXT,
                    submission_count INTEGER DEFAULT 0,
                    created_at TEXT
                )
            ''')
            
            # 班级表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS classes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_name TEXT UNIQUE,
                    grade TEXT,
                    student_count INTEGER DEFAULT 0,
                    created_at TEXT
                )
            ''')
            
            # ====== 题库管理新增表 ======
            
            # 题库表（AI生成的题目）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS question_bank (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_text TEXT NOT NULL,
                    question_type TEXT,
                    knowledge_point TEXT NOT NULL,
                    difficulty INTEGER DEFAULT 1,
                    correct_answer TEXT,
                    options TEXT,
                    explanation TEXT,
                    source TEXT DEFAULT 'AI生成',
                    created_by TEXT,
                    created_at TEXT,
                    times_used INTEGER DEFAULT 0,
                    times_correct INTEGER DEFAULT 0
                )
            ''')
            
            # 练习记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS practice_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    question_id INTEGER,
                    student_answer TEXT,
                    is_correct INTEGER DEFAULT 0,
                    practice_date TEXT,
                    difficulty_level INTEGER DEFAULT 1,
                    FOREIGN KEY (student_id) REFERENCES students(id),
                    FOREIGN KEY (question_id) REFERENCES question_bank(id)
                )
            ''')
            
            # 知识点掌握表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS knowledge_mastery (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    knowledge_point TEXT NOT NULL,
                    total_attempts INTEGER DEFAULT 0,
                    correct_count INTEGER DEFAULT 0,
                    mastery_level TEXT DEFAULT '未掌握',
                    last_practice_date TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(id)
                )
            ''')
            
            # 练习任务表（保存每次练习的题目）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS practice_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    knowledge_point TEXT,
                    question_ids TEXT,
                    total_questions INTEGER DEFAULT 0,
                    correct_answers INTEGER DEFAULT 0,
                    status TEXT DEFAULT '进行中',
                    started_at TEXT,
                    completed_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(id)
                )
            ''')
            
            # ====== 教师管理新增表 ======
            
            # 教师表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teachers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'teacher',
                    phone TEXT,
                    is_active INTEGER DEFAULT 1,
                    last_login TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 教师-班级关联表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teacher_classes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id INTEGER NOT NULL,
                    class_id INTEGER NOT NULL,
                    is_primary INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (teacher_id) REFERENCES teachers(id),
                    FOREIGN KEY (class_id) REFERENCES classes(id),
                    UNIQUE(teacher_id, class_id)
                )
            ''')
            
            # 操作日志表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS operation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id INTEGER,
                    operation TEXT,
                    target_type TEXT,
                    target_id INTEGER,
                    details TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 检查是否需要添加新字段到现有表
            try:
                cursor.execute('ALTER TABLE classes ADD COLUMN grade TEXT')
            except:
                pass
            try:
                cursor.execute('ALTER TABLE classes ADD COLUMN academic_year TEXT DEFAULT "2025-2026"')
            except:
                pass
            try:
                cursor.execute('ALTER TABLE error_diagnoses ADD COLUMN teacher_id INTEGER')
            except:
                pass
            
            # 创建默认管理员账号（如果不存在）
            cursor.execute('SELECT COUNT(*) FROM teachers WHERE username = "admin"')
            if cursor.fetchone()[0] == 0:
                import hashlib
                password_hash = hashlib.sha256('admin123'.encode()).hexdigest()
                cursor.execute('''
                    INSERT INTO teachers (name, username, password_hash, role)
                    VALUES (?, ?, ?, ?)
                ''', ('系统管理员', 'admin', password_hash, 'admin'))
    
    # ========== 学生管理 ==========
    
    def add_student(self, student: Student) -> int:
        """添加学生"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO students (name, student_id, class_name, grade, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (student.name, student.student_id, student.class_name, student.grade, student.created_at))
            return cursor.lastrowid
    
    def get_students(self, class_name: str = None) -> List[Dict]:
        """获取学生列表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if class_name:
                cursor.execute('SELECT * FROM students WHERE class_name = ? ORDER BY student_id', (class_name,))
            else:
                cursor.execute('SELECT * FROM students ORDER BY class_name, student_id')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_student(self, student_id: int) -> Optional[Dict]:
        """获取单个学生"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM students WHERE id = ?', (student_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_student(self, student_id: int, **kwargs):
        """更新学生信息"""
        fields = ', '.join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [student_id]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'UPDATE students SET {fields} WHERE id = ?', values)
    
    def delete_student(self, student_id: int):
        """删除学生"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM students WHERE id = ?', (student_id,))
    
    # ========== 班级管理 ==========
    
    def add_class(self, class_name: str, grade: str = "高一") -> int:
        """添加班级"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO classes (class_name, grade, created_at)
                VALUES (?, ?, datetime('now'))
            ''', (class_name, grade))
            return cursor.lastrowid
    
    def get_classes(self, grade: str = None) -> List[Dict]:
        """获取班级列表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if grade:
                cursor.execute('SELECT * FROM classes WHERE grade = ? ORDER BY class_name', (grade,))
            else:
                cursor.execute('SELECT * FROM classes ORDER BY class_name')
            return [dict(row) for row in cursor.fetchall()]
    
    # ========== 题目管理 ==========
    
    def add_question(self, question: Question) -> int:
        """添加题目"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO questions (question_text, question_type, knowledge_point, difficulty, correct_answer, source)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                question.question_text, question.question_type, question.knowledge_point,
                question.difficulty, question.correct_answer, question.source
            ))
            return cursor.lastrowid
    
    def get_questions(self, knowledge_point: str = None, limit: int = 100) -> List[Dict]:
        """获取题目列表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if knowledge_point:
                cursor.execute('''
                    SELECT * FROM questions 
                    WHERE knowledge_point = ? 
                    ORDER BY difficulty, id
                    LIMIT ?
                ''', (knowledge_point, limit))
            else:
                cursor.execute('SELECT * FROM questions ORDER BY knowledge_point, difficulty LIMIT ?', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_question(self, question_id: int) -> Optional[Dict]:
        """获取单个题目"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM questions WHERE id = ?', (question_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    # ========== 答题记录管理 ==========
    
    def add_answer(self, answer: StudentAnswer) -> int:
        """添加答题记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO student_answers (student_id, question_id, student_answer, is_correct, submitted_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                answer.student_id, answer.question_id, answer.student_answer,
                1 if answer.is_correct else 0, answer.submitted_at
            ))
            return cursor.lastrowid
    
    def get_student_answers(self, student_id: int) -> List[Dict]:
        """获取学生的答题记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sa.*, q.question_text, q.knowledge_point, q.correct_answer, q.question_type
                FROM student_answers sa
                JOIN questions q ON sa.question_id = q.id
                WHERE sa.student_id = ?
                ORDER BY sa.submitted_at DESC
            ''', (student_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_incorrect_answers(self, student_id: int) -> List[Dict]:
        """获取学生的错题记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sa.*, q.question_text, q.knowledge_point, q.correct_answer, q.question_type
                FROM student_answers sa
                JOIN questions q ON sa.question_id = q.id
                WHERE sa.student_id = ? AND sa.is_correct = 0
                ORDER BY sa.submitted_at DESC
            ''', (student_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ========== 错因诊断管理 ==========
    
    def add_diagnosis(self, diagnosis: ErrorDiagnosis) -> int:
        """添加诊断结果（含完整题目信息）"""
        from datetime import datetime
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO error_diagnoses 
                (question_id, student_id, error_type, error_type_name, diagnosis_detail, knowledge_gaps, suggestion, diagnosed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                diagnosis.question_id, diagnosis.student_id, diagnosis.error_type,
                diagnosis.error_type_name, diagnosis.diagnosis_detail,
                json.dumps(diagnosis.knowledge_gaps, ensure_ascii=False),
                diagnosis.suggestion, diagnosis.diagnosed_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            return cursor.lastrowid
    
    def add_diagnosis_full(self, student_id: int, question_text: str, student_answer: str,
                           correct_answer: str, knowledge_point: str,
                           error_type: str, error_type_name: str,
                           diagnosis_detail: str, knowledge_gaps: list, suggestion: str) -> int:
        """添加完整诊断记录（含题目原文，不依赖questions表）"""
        from datetime import datetime
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO error_diagnoses 
                (question_id, student_id, error_type, error_type_name, diagnosis_detail, 
                 knowledge_gaps, suggestion, diagnosed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                0, student_id, error_type, error_type_name, diagnosis_detail,
                json.dumps(knowledge_gaps, ensure_ascii=False),
                suggestion, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            diag_id = cursor.lastrowid
            
            # 同时保存题目到questions表（如果不存在）
            cursor.execute('''
                INSERT OR IGNORE INTO questions (question_text, question_type, knowledge_point, correct_answer, source)
                VALUES (?, ?, ?, ?, ?)
            ''', (question_text, '诊断题', knowledge_point, correct_answer, '错题诊断'))
            
            # 更新诊断记录的question_id
            cursor.execute('SELECT id FROM questions WHERE question_text = ? AND knowledge_point = ? LIMIT 1',
                          (question_text, knowledge_point))
            q_row = cursor.fetchone()
            if q_row:
                cursor.execute('UPDATE error_diagnoses SET question_id = ? WHERE id = ?', (q_row['id'], diag_id))
            
            return diag_id
    
    def get_all_diagnoses(self, student_id: int = None, class_name: str = None, 
                          knowledge_point: str = None, limit: int = 100) -> List[Dict]:
        """获取诊断记录（支持多条件筛选）"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            sql = '''
                SELECT ed.*, s.name as student_name, s.class_name, s.student_id as student_no,
                       q.question_text, q.knowledge_point
                FROM error_diagnoses ed
                LEFT JOIN students s ON ed.student_id = s.id
                LEFT JOIN questions q ON ed.question_id = q.id
                WHERE 1=1
            '''
            params = []
            
            if student_id:
                sql += ' AND ed.student_id = ?'
                params.append(student_id)
            elif class_name:
                sql += ' AND s.class_name = ?'
                params.append(class_name)
            
            if knowledge_point:
                sql += ' AND q.knowledge_point = ?'
                params.append(knowledge_point)
            
            sql += ' ORDER BY ed.diagnosed_at DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(sql, params)
            results = [dict(row) for row in cursor.fetchall()]
            for r in results:
                if r.get('knowledge_gaps'):
                    try:
                        r['knowledge_gaps'] = json.loads(r['knowledge_gaps'])
                    except:
                        r['knowledge_gaps'] = []
            return results
    
    def get_student_diagnoses(self, student_id: int) -> List[Dict]:
        """获取学生的诊断记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT ed.*, COALESCE(q.question_text, ed.diagnosis_detail) as question_text, 
                       COALESCE(q.knowledge_point, '') as knowledge_point
                FROM error_diagnoses ed
                LEFT JOIN questions q ON ed.question_id = q.id
                WHERE ed.student_id = ?
                ORDER BY ed.diagnosed_at DESC
            ''', (student_id,))
            results = [dict(row) for row in cursor.fetchall()]
            for r in results:
                if r.get('knowledge_gaps'):
                    try:
                        r['knowledge_gaps'] = json.loads(r['knowledge_gaps'])
                    except:
                        r['knowledge_gaps'] = []
            return results
    
    def get_student_knowledge_diagnosis_summary(self, student_id: int) -> List[Dict]:
        """获取学生各知识点的诊断汇总（用于学生维度诊断）"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    COALESCE(q.knowledge_point, 
                        CASE WHEN ed.knowledge_gaps != '' THEN ed.knowledge_gaps ELSE '综合' END
                    ) as knowledge_point,
                    COUNT(*) as diag_count,
                    ed.error_type_name,
                    GROUP_CONCAT(DISTINCT ed.error_type_name) as error_types,
                    MAX(ed.diagnosed_at) as last_diag_date
                FROM error_diagnoses ed
                LEFT JOIN questions q ON ed.question_id = q.id
                WHERE ed.student_id = ?
                GROUP BY knowledge_point
                ORDER BY diag_count DESC
            ''', (student_id,))
            
            results = []
            for row in cursor.fetchall():
                r = dict(row)
                # 解析knowledge_point（可能是JSON数组字符串）
                kp = r.get('knowledge_point', '')
                if kp and kp.startswith('['):
                    try:
                        kps = json.loads(kp)
                        r['knowledge_point'] = ', '.join(kps) if kps else '综合'
                    except:
                        pass
                results.append(r)
            return results
    
    def get_student_core_content_summary(self, student_id: int, knowledge_point: str) -> List[Dict]:
        """获取学生在指定知识点下的三级核心内容分布"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 先获取该学生该知识点的所有诊断记录
            cursor.execute('''
                SELECT 
                    ed.knowledge_gaps,
                    ed.diagnosis_detail,
                    ed.error_type_name,
                    ed.diagnosed_at
                FROM error_diagnoses ed
                WHERE ed.student_id = ?
                ORDER BY ed.diagnosed_at DESC
            ''', (student_id,))
            
            all_records = cursor.fetchall()
            
            # 在Python中过滤匹配的记录
            matched_records = []
            for row in all_records:
                r = dict(row)
                kg = r.get('knowledge_gaps', '')
                detail = r.get('diagnosis_detail', '')
                
                # 检查是否匹配该知识点
                matched = False
                if knowledge_point in kg or knowledge_point in detail:
                    matched = True
                # 也检查JSON数组中的每个元素
                if kg and kg.startswith('['):
                    try:
                        gaps = json.loads(kg)
                        for gap in gaps:
                            if knowledge_point in str(gap):
                                matched = True
                                break
                    except:
                        pass
                
                if matched:
                    matched_records.append(r)
            
            return matched_records
    
    def delete_diagnosis(self, diagnosis_id: int) -> bool:
        """删除单条诊断记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM error_diagnoses WHERE id = ?', (diagnosis_id,))
            return cursor.rowcount > 0
    
    def get_diagnosis_count(self, student_id: int = None) -> int:
        """获取诊断记录数量"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if student_id:
                cursor.execute('SELECT COUNT(*) as cnt FROM error_diagnoses WHERE student_id = ?', (student_id,))
            else:
                cursor.execute('SELECT COUNT(*) as cnt FROM error_diagnoses')
            return cursor.fetchone()['cnt']
    
    # ========== 数据管理 ==========
    
    def get_all_practice_records(self, limit: int = 1000) -> List[Dict]:
        """获取所有练习记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT ph.*, s.name as student_name, qb.question_text
                FROM practice_history ph
                LEFT JOIN students s ON ph.student_id = s.id
                LEFT JOIN question_bank qb ON ph.question_id = qb.id
                ORDER BY ph.practice_date DESC
                LIMIT ?
            ''', (limit,))
            results = []
            for row in cursor.fetchall():
                r = dict(row)
                results.append(r)
            return results
    
    def clear_students(self) -> int:
        """清空学生数据"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM students')
            return cursor.rowcount
    
    def clear_diagnoses(self) -> int:
        """清空诊断记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM error_diagnoses')
            return cursor.rowcount
    
    def clear_questions(self) -> int:
        """清空题库"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM question_bank')
            return cursor.rowcount
    
    def clear_practice_records(self) -> int:
        """清空练习记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM practice_history')
            return cursor.rowcount
    
    def clear_all_data(self) -> Dict:
        """清空所有数据"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 清空各表
            cursor.execute('DELETE FROM practice_history')
            practice_count = cursor.rowcount
            
            cursor.execute('DELETE FROM error_diagnoses')
            diagnosis_count = cursor.rowcount
            
            cursor.execute('DELETE FROM question_bank')
            question_count = cursor.rowcount
            
            cursor.execute('DELETE FROM students')
            student_count = cursor.rowcount
            
            cursor.execute('DELETE FROM classes')
            class_count = cursor.rowcount
            
            return {
                'students': student_count,
                'diagnoses': diagnosis_count,
                'questions': question_count,
                'practice_records': practice_count,
                'classes': class_count
            }
    
    # ========== 统计数据 ==========
    
    def get_class_statistics(self, class_name: str) -> Dict:
        """获取班级统计数据"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取班级学生数
            cursor.execute('SELECT COUNT(*) as count FROM students WHERE class_name = ?', (class_name,))
            student_count = cursor.fetchone()['count']
            
            # 获取班级答题情况
            cursor.execute('''
                SELECT COUNT(*) as total, 
                       SUM(CASE WHEN sa.is_correct = 1 THEN 1 ELSE 0 END) as correct
                FROM student_answers sa
                JOIN students s ON sa.student_id = s.id
                WHERE s.class_name = ?
            ''', (class_name,))
            stats = cursor.fetchone()
            
            # 获取知识点掌握情况
            cursor.execute('''
                SELECT q.knowledge_point, 
                       COUNT(*) as total,
                       SUM(CASE WHEN sa.is_correct = 1 THEN 1 ELSE 0 END) as correct
                FROM student_answers sa
                JOIN questions q ON sa.question_id = q.id
                JOIN students s ON sa.student_id = s.id
                WHERE s.class_name = ?
                GROUP BY q.knowledge_point
            ''', (class_name,))
            knowledge_stats = [dict(row) for row in cursor.fetchall()]
            
            return {
                'student_count': student_count,
                'total_questions': stats['total'] or 0,
                'correct_count': stats['correct'] or 0,
                'accuracy_rate': round((stats['correct'] or 0) / (stats['total'] or 1) * 100, 1),
                'knowledge_stats': knowledge_stats
            }
    
    # ========== 题库管理 ==========
    
    def add_question_to_bank(self, question: Dict, created_by: str = "系统") -> int:
        """
        添加题目到题库
        
        Args:
            question: 题目字典，包含question_text, knowledge_point, difficulty等
            created_by: 创建者
            
        Returns:
            题目ID
        """
        from datetime import datetime
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO question_bank 
                (question_text, question_type, knowledge_point, difficulty, correct_answer, options, explanation, source, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                question.get('question_text', ''),
                question.get('question_type', ''),
                question.get('knowledge_point', ''),
                question.get('difficulty', 1),
                question.get('answer', ''),
                json.dumps(question.get('options', []), ensure_ascii=False) if question.get('options') else '',
                question.get('explanation', ''),
                'AI生成',
                created_by,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            return cursor.lastrowid
    
    def get_bank_questions(self, knowledge_point: str = None, difficulty: int = None, limit: int = 100) -> List[Dict]:
        """获取题库题目"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            sql = 'SELECT * FROM question_bank WHERE 1=1'
            params = []
            
            if knowledge_point:
                sql += ' AND knowledge_point = ?'
                params.append(knowledge_point)
            
            if difficulty:
                sql += ' AND difficulty = ?'
                params.append(difficulty)
            
            sql += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(sql, params)
            results = [dict(row) for row in cursor.fetchall()]
            
            # 解析options JSON
            for r in results:
                if r.get('options'):
                    try:
                        r['options'] = json.loads(r['options'])
                    except:
                        r['options'] = []
            
            return results
    
    def get_bank_question_by_id(self, question_id: int) -> Optional[Dict]:
        """根据ID获取题库题目"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM question_bank WHERE id = ?', (question_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                if result.get('options'):
                    try:
                        result['options'] = json.loads(result['options'])
                    except:
                        result['options'] = []
                return result
            return None
    
    def update_question_stats(self, question_id: int, is_correct: bool):
        """更新题目使用统计"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if is_correct:
                cursor.execute('''
                    UPDATE question_bank 
                    SET times_used = times_used + 1, times_correct = times_correct + 1
                    WHERE id = ?
                ''', (question_id,))
            else:
                cursor.execute('''
                    UPDATE question_bank 
                    SET times_used = times_used + 1
                    WHERE id = ?
                ''', (question_id,))
    
    def get_knowledge_stats(self, knowledge_point: str = None) -> List[Dict]:
        """获取知识点统计"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if knowledge_point:
                # 指定知识点的统计
                cursor.execute('''
                    SELECT 
                        knowledge_point,
                        COUNT(*) as total_questions,
                        SUM(times_used) as total_attempts,
                        SUM(times_correct) as total_correct,
                        CASE WHEN SUM(times_used) > 0 
                             THEN ROUND(CAST(SUM(times_correct) AS FLOAT) / SUM(times_used) * 100, 1)
                             ELSE 0 END as accuracy_rate
                    FROM question_bank
                    WHERE knowledge_point = ?
                    GROUP BY knowledge_point
                ''', (knowledge_point,))
            else:
                # 所有知识点的统计
                cursor.execute('''
                    SELECT 
                        knowledge_point,
                        COUNT(*) as total_questions,
                        SUM(times_used) as total_attempts,
                        SUM(times_correct) as total_correct,
                        CASE WHEN SUM(times_used) > 0 
                             THEN ROUND(CAST(SUM(times_correct) AS FLOAT) / SUM(times_used) * 100, 1)
                             ELSE 0 END as accuracy_rate
                    FROM question_bank
                    GROUP BY knowledge_point
                    ORDER BY accuracy_rate ASC
                ''')
            
            return [dict(row) for row in cursor.fetchall()]
    
    # ========== 练习记录管理 ==========
    
    def add_practice_record(self, student_id: int, question_id: int, student_answer: str, is_correct: bool, difficulty_level: int = 1) -> int:
        """添加练习记录"""
        from datetime import datetime
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO practice_history (student_id, question_id, student_answer, is_correct, practice_date, difficulty_level)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                student_id, question_id, student_answer,
                1 if is_correct else 0,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                difficulty_level
            ))
            
            # 更新题目统计（在同一个连接中执行，避免数据库锁定）
            if is_correct:
                cursor.execute('''
                    UPDATE question_bank 
                    SET times_used = times_used + 1, times_correct = times_correct + 1
                    WHERE id = ?
                ''', (question_id,))
            else:
                cursor.execute('''
                    UPDATE question_bank 
                    SET times_used = times_used + 1
                    WHERE id = ?
                ''', (question_id,))
            
            return cursor.lastrowid
    
    def get_student_practice_history(self, student_id: int, limit: int = 50) -> List[Dict]:
        """获取学生的练习历史"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT ph.*, qb.question_text, qb.knowledge_point, qb.correct_answer, qb.options, qb.explanation
                FROM practice_history ph
                JOIN question_bank qb ON ph.question_id = qb.id
                WHERE ph.student_id = ?
                ORDER BY ph.practice_date DESC
                LIMIT ?
            ''', (student_id, limit))
            
            results = [dict(row) for row in cursor.fetchall()]
            for r in results:
                if r.get('options'):
                    try:
                        r['options'] = json.loads(r['options'])
                    except:
                        r['options'] = []
            return results
    
    def get_student_knowledge_mastery(self, student_id: int) -> List[Dict]:
        """获取学生对各知识点的掌握情况"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    qb.knowledge_point,
                    COUNT(*) as total_attempts,
                    SUM(CASE WHEN ph.is_correct = 1 THEN 1 ELSE 0 END) as correct_count,
                    ROUND(CAST(SUM(CASE WHEN ph.is_correct = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 1) as accuracy_rate,
                    MAX(ph.practice_date) as last_practice_date
                FROM practice_history ph
                JOIN question_bank qb ON ph.question_id = qb.id
                WHERE ph.student_id = ?
                GROUP BY qb.knowledge_point
                ORDER BY accuracy_rate ASC
            ''', (student_id,))
            
            results = []
            for row in cursor.fetchall():
                r = dict(row)
                # 计算掌握等级
                accuracy = r.get('accuracy_rate', 0) or 0
                attempts = r.get('total_attempts', 0)
                
                if attempts == 0:
                    r['mastery_level'] = '未练习'
                elif accuracy >= 90 and attempts >= 3:
                    r['mastery_level'] = '🌟 熟练'
                elif accuracy >= 70 and attempts >= 2:
                    r['mastery_level'] = '👍 掌握'
                elif accuracy >= 50:
                    r['mastery_level'] = '💪 提升中'
                else:
                    r['mastery_level'] = '🔴 需加强'
                
                results.append(r)
            
            return results
    
    def get_class_knowledge_mastery(self, class_name: str) -> List[Dict]:
        """获取班级对各知识点的整体掌握情况"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    qb.knowledge_point,
                    COUNT(DISTINCT ph.student_id) as student_count,
                    COUNT(*) as total_attempts,
                    SUM(CASE WHEN ph.is_correct = 1 THEN 1 ELSE 0 END) as correct_count,
                    ROUND(CAST(SUM(CASE WHEN ph.is_correct = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 1) as accuracy_rate
                FROM practice_history ph
                JOIN question_bank qb ON ph.question_id = qb.id
                JOIN students s ON ph.student_id = s.id
                WHERE s.class_name = ?
                GROUP BY qb.knowledge_point
                ORDER BY accuracy_rate ASC
            ''', (class_name,))
            
            results = []
            for row in cursor.fetchall():
                r = dict(row)
                accuracy = r.get('accuracy_rate', 0) or 0
                student_count = r.get('student_count', 0)
                
                # 计算班级掌握等级
                if student_count == 0:
                    r['mastery_level'] = '未练习'
                elif accuracy >= 90:
                    r['mastery_level'] = '🌟 优秀'
                elif accuracy >= 70:
                    r['mastery_level'] = '👍 良好'
                elif accuracy >= 50:
                    r['mastery_level'] = '💪 一般'
                else:
                    r['mastery_level'] = '🔴 薄弱'
                
                results.append(r)
            
            return results
    
    def get_weak_students(self, knowledge_point: str, class_name: str = None) -> List[Dict]:
        """获取某知识点薄弱的学生"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if class_name:
                cursor.execute('''
                    SELECT 
                        s.id, s.name, s.class_name,
                        COUNT(*) as total_attempts,
                        SUM(CASE WHEN ph.is_correct = 1 THEN 1 ELSE 0 END) as correct_count,
                        ROUND(CAST(SUM(CASE WHEN ph.is_correct = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 1) as accuracy_rate
                    FROM practice_history ph
                    JOIN question_bank qb ON ph.question_id = qb.id
                    JOIN students s ON ph.student_id = s.id
                    WHERE qb.knowledge_point = ? AND s.class_name = ?
                    GROUP BY s.id
                    HAVING accuracy_rate < 70
                    ORDER BY accuracy_rate ASC
                ''', (knowledge_point, class_name))
            else:
                cursor.execute('''
                    SELECT 
                        s.id, s.name, s.class_name,
                        COUNT(*) as total_attempts,
                        SUM(CASE WHEN ph.is_correct = 1 THEN 1 ELSE 0 END) as correct_count,
                        ROUND(CAST(SUM(CASE WHEN ph.is_correct = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 1) as accuracy_rate
                    FROM practice_history ph
                    JOIN question_bank qb ON ph.question_id = qb.id
                    JOIN students s ON ph.student_id = s.id
                    WHERE qb.knowledge_point = ?
                    GROUP BY s.id
                    HAVING accuracy_rate < 70
                    ORDER BY accuracy_rate ASC
                ''', (knowledge_point,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    # ========== 教师管理 ==========
    
    def add_teacher(self, name: str, username: str, password: str, role: str = 'teacher', phone: str = None) -> int:
        """添加教师"""
        import hashlib
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO teachers (name, username, password_hash, role, phone)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, username, password_hash, role, phone))
            return cursor.lastrowid
    
    def verify_teacher(self, username: str, password: str) -> Optional[Dict]:
        """验证教师登录"""
        import hashlib
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM teachers 
                WHERE username = ? AND password_hash = ? AND is_active = 1
            ''', (username, password_hash))
            row = cursor.fetchone()
            if row:
                # 更新最后登录时间
                from datetime import datetime
                cursor.execute('''
                    UPDATE teachers SET last_login = ? WHERE id = ?
                ''', (datetime.now().isoformat(), row['id']))
                return dict(row)
            return None
    
    def get_teacher(self, teacher_id: int) -> Optional[Dict]:
        """获取单个教师"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM teachers WHERE id = ?', (teacher_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_teacher_by_username(self, username: str) -> Optional[Dict]:
        """通过用户名获取教师"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM teachers WHERE username = ?', (username,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_teachers(self) -> List[Dict]:
        """获取所有教师"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM teachers ORDER BY created_at DESC')
            return [dict(row) for row in cursor.fetchall()]
    
    def update_teacher(self, teacher_id: int, **kwargs):
        """更新教师信息"""
        # 如果更新密码，需要加密
        if 'password' in kwargs:
            import hashlib
            kwargs['password_hash'] = hashlib.sha256(kwargs.pop('password').encode()).hexdigest()
        
        fields = ', '.join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [teacher_id]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'UPDATE teachers SET {fields} WHERE id = ?', values)
    
    def delete_teacher(self, teacher_id: int):
        """删除教师"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 先删除关联的班级关系
            cursor.execute('DELETE FROM teacher_classes WHERE teacher_id = ?', (teacher_id,))
            # 再删除教师
            cursor.execute('DELETE FROM teachers WHERE id = ?', (teacher_id,))
    
    # ========== 教师-班级关联管理 ==========
    
    def assign_class_to_teacher(self, teacher_id: int, class_id: int, is_primary: bool = False):
        """分配班级给教师"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO teacher_classes (teacher_id, class_id, is_primary)
                    VALUES (?, ?, ?)
                ''', (teacher_id, class_id, 1 if is_primary else 0))
            except sqlite3.IntegrityError:
                # 已存在则更新
                cursor.execute('''
                    UPDATE teacher_classes SET is_primary = ?
                    WHERE teacher_id = ? AND class_id = ?
                ''', (1 if is_primary else 0, teacher_id, class_id))
    
    def remove_class_from_teacher(self, teacher_id: int, class_id: int):
        """移除教师的班级"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM teacher_classes WHERE teacher_id = ? AND class_id = ?
            ''', (teacher_id, class_id))
    
    def get_teacher_classes(self, teacher_id: int) -> List[Dict]:
        """获取教师负责的班级"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.*, tc.is_primary 
                FROM classes c
                JOIN teacher_classes tc ON c.id = tc.class_id
                WHERE tc.teacher_id = ?
                ORDER BY c.class_name
            ''', (teacher_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_class_teachers(self, class_id: int) -> List[Dict]:
        """获取班级的教师"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.*, tc.is_primary
                FROM teachers t
                JOIN teacher_classes tc ON t.id = tc.teacher_id
                WHERE tc.class_id = ? AND t.is_active = 1
                ORDER BY tc.is_primary DESC
            ''', (class_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_teacher_class_names(self, teacher_id: int) -> List[str]:
        """获取教师负责的班级名称列表"""
        classes = self.get_teacher_classes(teacher_id)
        return [c['class_name'] for c in classes]
    
    def is_teacher_admin(self, teacher_id: int) -> bool:
        """检查教师是否为管理员"""
        teacher = self.get_teacher(teacher_id)
        return teacher and teacher.get('role') == 'admin'
    
    def teacher_has_class_permission(self, teacher_id: int, class_name: str) -> bool:
        """检查教师是否有某班级的权限"""
        # 管理员有所有权限
        if self.is_teacher_admin(teacher_id):
            return True
        # 普通教师检查是否负责该班级
        class_names = self.get_teacher_class_names(teacher_id)
        return class_name in class_names

# 全局数据库实例
db = Database()
