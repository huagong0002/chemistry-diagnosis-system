# -*- coding: utf-8 -*-
"""
知识点库管理模块 - 三层结构
支持自定义添加、导入、删除知识点
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd
import io

# 知识点库文件路径
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
KNOWLEDGE_FILE = DATA_DIR / "knowledge_points.json"
KNOWLEDGE_STRUCTURE_FILE = DATA_DIR / "knowledge_structure.json"

# 默认三层知识结构（内置）
DEFAULT_KNOWLEDGE_STRUCTURE = {
    "氧化还原反应": {
        "code": "YHYY",
        "points": [
            {
                "name": "氧化还原反应基本概念",
                "core_contents": [
                    {
                        "name": "氧化反应与还原反应",
                        "keywords": ["氧化反应", "还原反应", "电子转移", "化合价变化"],
                        "common_errors": ["混淆氧化反应和还原反应", "电子转移方向判断错误"]
                    },
                    {
                        "name": "氧化剂与还原剂",
                        "keywords": ["氧化剂", "还原剂", "被氧化", "被还原"],
                        "common_errors": ["氧化剂和还原剂判断错误", "氧化性强弱比较错误"]
                    }
                ]
            },
            {
                "name": "氧化还原反应方程式配平",
                "core_contents": [
                    {
                        "name": "电子得失法配平",
                        "keywords": ["电子得失守恒", "化合价升降法", "最小公倍数"],
                        "common_errors": ["电子转移数目计算错误", "配平时原子不守恒"]
                    }
                ]
            }
        ]
    },
    "离子反应": {
        "code": "LYFY",
        "points": [
            {
                "name": "电解质与非电解质",
                "core_contents": [
                    {
                        "name": "电解质概念",
                        "keywords": ["电解质", "非电解质", "强电解质", "弱电解质"],
                        "common_errors": ["不会判断电解质", "强弱电解质混淆"]
                    }
                ]
            },
            {
                "name": "离子方程式书写",
                "core_contents": [
                    {
                        "name": "离子方程式书写规则",
                        "keywords": ["拆写规则", "离子方程式", "沉淀", "气体", "弱电解质"],
                        "common_errors": ["拆写不符合规则", "忽略反应条件", "电荷不守恒"]
                    }
                ]
            }
        ]
    },
    "物质的量": {
        "code": "WDDL",
        "points": [
            {
                "name": "物质的量基本概念",
                "core_contents": [
                    {
                        "name": "摩尔与阿伏伽德罗常数",
                        "keywords": ["摩尔", "阿伏伽德罗常数", "6.02×10²³", "微粒数"],
                        "common_errors": ["概念理解不到位", "单位换算错误"]
                    }
                ]
            },
            {
                "name": "物质的量浓度计算",
                "core_contents": [
                    {
                        "name": "物质的量浓度",
                        "keywords": ["物质的量浓度", "摩尔质量", "溶液体积", "质量分数"],
                        "common_errors": ["公式混淆", "单位换算错误", "溶液体积与溶剂体积混淆"]
                    }
                ]
            }
        ]
    }
}


# ========== 三层结构管理 ==========

def load_knowledge_structure() -> Dict[str, Any]:
    """加载三层知识结构，优先从文件加载，否则使用默认值"""
    if KNOWLEDGE_STRUCTURE_FILE.exists():
        try:
            with open(KNOWLEDGE_STRUCTURE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载知识结构失败: {e}")
            return DEFAULT_KNOWLEDGE_STRUCTURE.copy()
    return DEFAULT_KNOWLEDGE_STRUCTURE.copy()


def save_knowledge_structure(structure: Dict[str, Any]) -> bool:
    """保存三层知识结构到文件"""
    try:
        with open(KNOWLEDGE_STRUCTURE_FILE, 'w', encoding='utf-8') as f:
            json.dump(structure, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存知识结构失败: {e}")
        return False


def add_knowledge_chapter(chapter_name: str, code: str, points: List[Dict] = None) -> bool:
    """添加知识章节（一级）"""
    structure = load_knowledge_structure()
    
    structure[chapter_name] = {
        "code": code,
        "points": points or []
    }
    
    return save_knowledge_structure(structure)


def add_knowledge_point(chapter_name: str, point_name: str, core_contents: List[Dict] = None) -> bool:
    """添加知识点（二级）到指定章节"""
    structure = load_knowledge_structure()
    
    if chapter_name not in structure:
        return False
    
    if "points" not in structure[chapter_name]:
        structure[chapter_name]["points"] = []
    
    structure[chapter_name]["points"].append({
        "name": point_name,
        "core_contents": core_contents or []
    })
    
    return save_knowledge_structure(structure)


def add_core_content(chapter_name: str, point_name: str, core_name: str,
                     keywords: List[str], common_errors: List[str]) -> bool:
    """添加核心内容（三级）到指定知识点"""
    structure = load_knowledge_structure()
    
    if chapter_name not in structure:
        return False
    
    chapter = structure[chapter_name]
    if "points" not in chapter:
        return False
    
    for point in chapter["points"]:
        if point.get("name") == point_name:
            if "core_contents" not in point:
                point["core_contents"] = []
            
            point["core_contents"].append({
                "name": core_name,
                "keywords": keywords,
                "common_errors": common_errors
            })
            return save_knowledge_structure(structure)
    
    return False


def delete_knowledge_chapter(chapter_name: str) -> bool:
    """删除知识章节"""
    structure = load_knowledge_structure()
    
    if chapter_name in structure:
        del structure[chapter_name]
        return save_knowledge_structure(structure)
    return False


def update_knowledge_point(old_name: str, name: str, code: str,
                          keywords: List[str], common_errors: List[str]) -> bool:
    """兼容旧版：更新知识点（更新章节名称和编码）"""
    structure = load_knowledge_structure()
    
    if old_name in structure:
        # 如果名称改变，更新key
        if old_name != name:
            structure[name] = structure.pop(old_name)
        structure[name]["code"] = code
        return save_knowledge_structure(structure)
    return False


def delete_knowledge_point(chapter_name: str, point_name: str = None) -> bool:
    """删除知识点或章节"""
    structure = load_knowledge_structure()
    
    # 如果只提供章节名，删除整个章节
    if point_name is None:
        if chapter_name in structure:
            del structure[chapter_name]
            return save_knowledge_structure(structure)
        return False
    
    # 删除指定章节下的知识点
    if chapter_name in structure and "points" in structure[chapter_name]:
        chapter = structure[chapter_name]
        chapter["points"] = [p for p in chapter["points"] if p.get("name") != point_name]
        return save_knowledge_structure(structure)
    
    return False


def delete_all_knowledge_points() -> bool:
    """一键删除所有自定义知识点，恢复默认"""
    try:
        if KNOWLEDGE_STRUCTURE_FILE.exists():
            KNOWLEDGE_STRUCTURE_FILE.unlink()
        return True
    except Exception as e:
        print(f"删除知识结构失败: {e}")
        return False


def validate_knowledge_point(name: str, code: str, keywords: List[str],
                            common_errors: List[str]) -> tuple[bool, str]:
    """验证知识点数据是否有效"""
    if not name or not name.strip():
        return False, "名称不能为空"
    
    if not code or not code.strip():
        return False, "编码不能为空"
    
    if len(code) > 10:
        return False, "编码不能超过10个字符"
    
    if not keywords or len(keywords) == 0:
        return False, "关键词不能为空"
    
    valid_keywords = [k for k in keywords if k and k.strip()]
    if len(valid_keywords) == 0:
        return False, "关键词不能全部为空"
    
    return True, "验证通过"


# ========== 导入导出 ==========

def get_excel_template() -> bytes:
    """生成三层结构的Excel导入模板"""
    template_data = {
        '一级·知识章节': ['氧化还原反应', '氧化还原反应', '离子反应'],
        '章节编码': ['YHYY', 'YHYY', 'LYFY'],
        '二级·知识点': ['氧化还原反应基本概念', '氧化还原反应方程式配平', '电解质与非电解质'],
        '三级·核心内容': ['氧化反应与还原反应', '电子得失法配平', '电解质概念'],
        '关键词': ['氧化反应,还原反应,电子转移', '电子得失守恒,化合价升降法', '电解质,非电解质,强弱电解质'],
        '常见错误': ['混淆氧化反应和还原反应', '电子转移数目计算错误', '不会判断电解质']
    }
    
    df = pd.DataFrame(template_data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='三层知识库模板')
        
        # 添加说明sheet
        instructions = pd.DataFrame({
            '字段说明': [
                '一级·知识章节: 必填，知识章节的名称，如：氧化还原反应',
                '章节编码: 必填，章节的唯一编码（建议英文或数字），如：YHYY',
                '二级·知识点: 必填，知识点名称，如：氧化还原反应基本概念',
                '三级·核心内容: 必填，核心内容名称，如：氧化反应与还原反应',
                '关键词: 必填，多个关键词用逗号分隔',
                '常见错误: 必填，多个错误用逗号分隔'
            ]
        })
        instructions.to_excel(writer, index=False, sheet_name='填写说明')
    
    return output.getvalue()


def import_from_excel(file_content: bytes) -> tuple[bool, str, List[Dict]]:
    """从Excel文件导入三层结构知识点"""
    try:
        df = pd.read_excel(io.BytesIO(file_content))
        
        # 检查必要的列
        required_cols = ['一级·知识章节', '章节编码', '二级·知识点', '三级·核心内容', '关键词', '常见错误']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            return False, f"缺少必要的列: {', '.join(missing_cols)}", []
        
        imported_items = []
        errors = []
        
        for idx, row in df.iterrows():
            try:
                chapter_name = str(row['一级·知识章节']).strip()
                chapter_code = str(row['章节编码']).strip()
                point_name = str(row['二级·知识点']).strip()
                core_name = str(row['三级·核心内容']).strip()
                keywords_str = str(row['关键词'])
                keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
                errors_str = str(row['常见错误'])
                common_errors = [e.strip() for e in errors_str.split(',') if e.strip()]
                
                if not chapter_name or not chapter_code or not point_name or not core_name:
                    errors.append(f"第{idx+2}行: 必填字段不能为空")
                    continue
                
                imported_items.append({
                    'chapter_name': chapter_name,
                    'chapter_code': chapter_code,
                    'point_name': point_name,
                    'core_name': core_name,
                    'keywords': keywords,
                    'common_errors': common_errors
                })
            except Exception as e:
                errors.append(f"第{idx+2}行: 解析错误 - {str(e)}")
        
        if errors:
            return False, f"导入完成，但有{len(errors)}条错误:\n" + "\n".join(errors[:5]), imported_items
        
        return True, f"成功导入 {len(imported_items)} 条核心内容", imported_items
        
    except Exception as e:
        return False, f"文件解析失败: {str(e)}", []


def confirm_import(items: List[Dict]) -> tuple[int, int]:
    """确认导入三层结构知识点"""
    success_count = 0
    fail_count = 0
    
    structure = load_knowledge_structure()
    
    for item in items:
        try:
            chapter_name = item['chapter_name']
            chapter_code = item['chapter_code']
            point_name = item['point_name']
            core_name = item['core_name']
            keywords = item['keywords']
            common_errors = item['common_errors']
            
            # 确保章节存在
            if chapter_name not in structure:
                structure[chapter_name] = {
                    "code": chapter_code,
                    "points": []
                }
            
            chapter = structure[chapter_name]
            
            # 查找或创建知识点
            point = None
            for p in chapter.get("points", []):
                if p.get("name") == point_name:
                    point = p
                    break
            
            if point is None:
                point = {"name": point_name, "core_contents": []}
                chapter["points"].append(point)
            
            # 添加核心内容
            if "core_contents" not in point:
                point["core_contents"] = []
            
            point["core_contents"].append({
                "name": core_name,
                "keywords": keywords,
                "common_errors": common_errors
            })
            
            success_count += 1
        except Exception as e:
            print(f"导入失败: {e}")
            fail_count += 1
    
    if success_count > 0:
        save_knowledge_structure(structure)
    
    return success_count, fail_count


def get_json_template() -> str:
    """生成JSON导入模板"""
    template = {
        "氧化还原反应": {
            "code": "YHYY",
            "points": [
                {
                    "name": "氧化还原反应基本概念",
                    "core_contents": [
                        {
                            "name": "氧化反应与还原反应",
                            "keywords": ["氧化反应", "还原反应", "电子转移"],
                            "common_errors": ["混淆氧化反应和还原反应"]
                        }
                    ]
                }
            ]
        }
    }
    return json.dumps(template, ensure_ascii=False, indent=2)


def import_from_json(file_content: str) -> tuple[bool, str, List[Dict]]:
    """从JSON文件导入三层结构知识点"""
    try:
        data = json.loads(file_content)
        
        imported_items = []
        errors = []
        
        if isinstance(data, dict):
            for chapter_name, chapter_info in data.items():
                try:
                    chapter_code = chapter_info.get('code', '')
                    points = chapter_info.get('points', [])
                    
                    for point in points:
                        point_name = point.get('name', '')
                        core_contents = point.get('core_contents', [])
                        
                        for core in core_contents:
                            core_name = core.get('name', '')
                            keywords = core.get('keywords', [])
                            common_errors = core.get('common_errors', [])
                            
                            imported_items.append({
                                'chapter_name': chapter_name,
                                'chapter_code': chapter_code,
                                'point_name': point_name,
                                'core_name': core_name,
                                'keywords': keywords,
                                'common_errors': common_errors
                            })
                except Exception as e:
                    errors.append(f"'{chapter_name}': 解析错误 - {str(e)}")
        
        if errors:
            return False, f"导入完成，但有{len(errors)}条错误:\n" + "\n".join(errors[:5]), imported_items
        
        return True, f"成功解析 {len(imported_items)} 条核心内容", imported_items
        
    except json.JSONDecodeError as e:
        return False, f"JSON格式错误: {str(e)}", []
    except Exception as e:
        return False, f"解析失败: {str(e)}", []


# ========== 兼容旧版 ==========

def load_knowledge_points() -> Dict[str, Any]:
    """兼容旧版：加载知识点库（扁平结构）"""
    # 将三层结构转换为扁平结构
    structure = load_knowledge_structure()
    flat_points = {}
    
    for chapter_name, chapter_info in structure.items():
        code = chapter_info.get('code', '')
        for point in chapter_info.get('points', []):
            point_name = point.get('name', '')
            # 收集所有核心内容的关键词和错误
            all_keywords = []
            all_errors = []
            for core in point.get('core_contents', []):
                all_keywords.extend(core.get('keywords', []))
                all_errors.extend(core.get('common_errors', []))
            
            full_name = f"{chapter_name} - {point_name}"
            flat_points[full_name] = {
                "code": code,
                "keywords": list(set(all_keywords)),
                "common_errors": list(set(all_errors))
            }
    
    return flat_points


def get_chemistry_knowledge_points() -> Dict[str, Any]:
    """获取当前知识点库（供config.py使用）"""
    return load_knowledge_points()
