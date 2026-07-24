# -*- coding: utf-8 -*-
"""
化学错题智能诊断系统 - Streamlit主界面
低门槛Web应用，无需专业编程知识即可使用
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os
import io

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from config import STREAMLIT_CONFIG, ERROR_TYPES

# 动态加载知识点（确保系统设置修改后能同步更新）
def get_knowledge_points():
    """动态加载知识点库"""
    from knowledge_manager import load_knowledge_points
    return load_knowledge_points()

# 兼容旧代码的变量（延迟加载）
CHEMISTRY_KNOWLEDGE_POINTS = None

def get_kp():
    """获取知识点（每次都重新加载）"""
    return get_knowledge_points()
from database import db
from models import Student, Question, StudentAnswer, ErrorDiagnosis
from ai_service import get_ai_service
import ai_service as _ai_module

# ========== LaTeX渲染辅助函数 ==========
import re
import streamlit.components.v1 as components

# 全局计数器，确保每个HTML组件有唯一ID
_latex_counter = 0

def _next_id():
    global _latex_counter
    _latex_counter += 1
    return f"latex_render_{_latex_counter}"

def process_ion_data_tags(text):
    """处理文本中的[ION_DATA: ...]标签，替换为base64 SVG图片"""
    if not text or '[ION_DATA:' not in text:
        return text
    
    import re
    import base64
    
    def generate_ion_svg_base64(ion_symbol, charge, electrons):
        """根据参数生成原子/离子结构示意图的base64 SVG图片（右半圆弧风格，紧凑版）"""
        cx, cy = 50, 35
        nucleus_r = 12
        first_r = 16
        r_step = 10
        
        max_r = first_r + (len(electrons) - 1) * r_step if electrons else first_r
        svg_w = cx + max_r + 30
        svg_h = 70
        
        parts = []
        parts.append('<svg xmlns="http://www.w3.org/2000/svg" width="' + str(svg_w) + '" height="' + str(svg_h) + '" viewBox="0 0 ' + str(svg_w) + ' ' + str(svg_h) + '">')
        parts.append('<text x="' + str(cx - nucleus_r - 5) + '" y="' + str(cy + 5) + '" text-anchor="end" font-size="16" font-weight="bold" font-family="serif">' + ion_symbol + '</text>')
        parts.append('<circle cx="' + str(cx) + '" cy="' + str(cy) + '" r="' + str(nucleus_r) + '" fill="white" stroke="black" stroke-width="1"/>')
        parts.append('<text x="' + str(cx) + '" y="' + str(cy + 5) + '" text-anchor="middle" font-size="12" font-weight="bold" font-family="serif">+' + str(charge) + '</text>')
        
        for i, num in enumerate(electrons):
            r = first_r + i * r_step
            y1 = cy - r
            y2 = cy + r
            parts.append('<path d="M ' + str(cx) + ' ' + str(y1) + ' A ' + str(r) + ' ' + str(r) + ' 0 0 1 ' + str(cx) + ' ' + str(y2) + '" fill="none" stroke="black" stroke-width="1"/>')
            parts.append('<text x="' + str(cx + r + 4) + '" y="' + str(cy + 4) + '" font-size="12" font-family="serif">' + str(num) + '</text>')
        
        parts.append('</svg>')
        svg_string = ''.join(parts)
        svg_bytes = svg_string.encode('utf-8')
        b64 = base64.b64encode(svg_bytes).decode('ascii')
        return '<img src="data:image/svg+xml;base64,' + b64 + '" style="display:inline-block;vertical-align:middle;height:45px;"/>'
    
    def replace_ion_data(match):
        ion_symbol = match.group(1).strip()
        charge = int(match.group(2).strip())
        electrons = [int(x.strip()) for x in match.group(3).split(',') if x.strip().isdigit()]
        if not electrons:
            return match.group(0)
        return generate_ion_svg_base64(ion_symbol, charge, electrons)
    
    return re.sub(
        r'\[ION_DATA:\s*([^,]+),\s*(\d+),\s*\[([\d,\s]+)\]\]',
        replace_ion_data,
        text
    )


def render_latex_html(text: str, font_size: str = "17px", line_height: str = "1.8", return_html: bool = False):
    """
    使用KaTeX+mhchem在iframe中渲染包含LaTeX化学式的文本。
    这是唯一可靠的渲染方式，因为st.latex()不支持 r'\ce{}' 命令。
    
    Args:
        text: 要渲染的文本
        font_size: 字体大小
        line_height: 行高
        return_html: 如果为True，返回处理后的HTML文本而不是渲染
    """
    if not text:
        return None if return_html else None
    
    uid = _next_id()
    
    # 处理没有$包裹的\ce{...}，将其包裹在$...$中
    # 先处理已经有$包裹的
    import re
    processed_text = text
    
    # 预处理：解析[ION_DATA: ...]标签，转换为base64 SVG图片
    processed_text = process_ion_data_tags(processed_text)
    
    # 兼容处理：将Unicode加热符号△替换为LaTeX格式\triangle
    processed_text = processed_text.replace('=[△]', '=[\\triangle]')
    processed_text = processed_text.replace('[△]', '[\\triangle]')
    
    # 匹配没有$包裹的\ce{...}（需要处理嵌套大括号）
    i = 0
    while True:
        ce_pos = processed_text.find(r'\ce{', i)
        if ce_pos == -1:
            break
        if ce_pos > 0 and processed_text[ce_pos-1] == '$':
            i = ce_pos + 4
            continue
        brace_count = 1
        j = ce_pos + 4
        while j < len(processed_text) and brace_count > 0:
            if processed_text[j] == '{':
                brace_count += 1
            elif processed_text[j] == '}':
                brace_count -= 1
            j += 1
        if brace_count == 0:
            processed_text = processed_text[:ce_pos] + '$' + processed_text[ce_pos:j] + '$' + processed_text[j:]
            i = j + 2
        else:
            i = ce_pos + 4
    
    # 根据内容长度估算初始高度
    estimated_lines = processed_text.count('\n') + processed_text.count('。') + processed_text.count('，') // 20 + 1
    div_count = processed_text.count('<div')
    if div_count > 0:
        total_lines = max(estimated_lines, div_count)
    else:
        char_lines = len(processed_text) // 50 + 1
        total_lines = max(estimated_lines, char_lines)
    height = min(max(total_lines * 28, 35), 500)
    
    # 如果包含原子结构示意图（img标签），适当增加高度
    if '<img' in processed_text and 'base64' in processed_text:
        img_count = processed_text.count('<img')
        height = max(height, 35 + img_count * 20)
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/mhchem.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
<style>
    body {{
        font-family: "Noto Sans CJK SC", -apple-system, "Microsoft YaHei", "PingFang SC", "WenQuanYi Micro Hei", sans-serif;
        font-size: {font_size};
        line-height: {line_height};
        color: #1a1a1a;
        margin: 2px 0;
        padding: 0;
        overflow: hidden;
    }}
    .katex {{ font-size: 1.15em; }}
</style>
</head>
<body>
<div id="{uid}">{processed_text}</div>
<script>
    renderMathInElement(document.getElementById("{uid}"), {{
        delimiters: [
            {{left: '$$', right: '$$', display: true}},
            {{left: '$', right: '$', display: false}}
        ],
        throwOnError: false
    }});
    // 渲染完成后，动态调整iframe高度匹配内容
    setTimeout(function() {{
        var el = document.getElementById("{uid}");
        if (el) {{
            var h = el.getBoundingClientRect().height;
            if (h > 0 && window.parent) {{
                // 使用Streamlit的iframe高度调整机制
                var iframe = window.frameElement;
                if (iframe) {{
                    iframe.style.height = (h + 8) + 'px';
                }}
            }}
        }}
    }}, 300);
</script>
</html>"""
    
    if return_html:
        return processed_text
    else:
        components.html(html_content, height=height, scrolling=False)

def render_latex_text(text: str, q_num: int = None):
    """
    渲染包含LaTeX的题目文本（带题号）
    """
    if not text:
        return
    
    prefix = f"<b>{q_num}.</b> " if q_num else ""
    render_latex_html(prefix + text, font_size="17px", line_height="1.8")

def render_option_latex(letter: str, text: str):
    """
    渲染单个选项（带字母标签）
    """
    if not text:
        return
    # 直接渲染，render_latex_html内部会处理原子结构示意图
    content = f"<b>{letter}.</b> {text}"
    render_latex_html(content, font_size="16px", line_height="1.7")

# ========== 页面配置 ==========
st.set_page_config(
    page_title=STREAMLIT_CONFIG["page_title"],
    page_icon=STREAMLIT_CONFIG["page_icon"],
    layout=STREAMLIT_CONFIG["layout"]
)

# ========== 自定义样式 ==========
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1a365d;
        text-align: center;
        padding: 1rem 0;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #4a5568;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f7fafc;
        border-radius: 10px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap-gap: 1rem;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 0.5rem 1rem;
    }
</style>

<!-- KaTeX LaTeX渲染支持 -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<!-- mhchem扩展用于化学式渲染 -->
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/mhchem.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"
    onload="renderMathInElement(document.body, {
        delimiters: [
            {left: '$$', right: '$$', display: true},
            {left: '$', right: '$', display: false}
        ],
        throwOnError: false,
        trust: true,
        strict: false
    });"></script>

<!-- 自定义样式优化LaTeX显示 -->
<style>
    .katex { font-size: 1.1em; }
    .katex-display { margin: 0.5em 0; }
    .question-text { font-size: 1.1em; line-height: 1.8; }
    .option-text { font-size: 1.05em; margin: 0.3em 0; }
</style>
""", unsafe_allow_html=True)

# ========== 初始化会话状态 ==========
if 'current_student' not in st.session_state:
    st.session_state.current_student = None
if 'ai_service' not in st.session_state:
    st.session_state.ai_service = None

# 教师登录相关会话状态
if 'teacher_id' not in st.session_state:
    st.session_state.teacher_id = None
if 'teacher_name' not in st.session_state:
    st.session_state.teacher_name = None
if 'teacher_role' not in st.session_state:
    st.session_state.teacher_role = None
if 'teacher_classes' not in st.session_state:
    st.session_state.teacher_classes = []
if 'is_logged_in' not in st.session_state:
    st.session_state.is_logged_in = False

# ========== 登录相关函数 ==========

def login_teacher(username, password):
    """验证教师登录"""
    teacher = db.verify_teacher(username, password)
    if teacher:
        st.session_state.teacher_id = teacher['id']
        st.session_state.teacher_name = teacher['name']
        st.session_state.teacher_role = teacher['role']
        st.session_state.is_logged_in = True
        # 获取教师负责的班级
        classes = db.get_teacher_class_names(teacher['id'])
        st.session_state.teacher_classes = classes
        return True
    return False

def logout_teacher():
    """退出登录"""
    st.session_state.teacher_id = None
    st.session_state.teacher_name = None
    st.session_state.teacher_role = None
    st.session_state.teacher_classes = []
    st.session_state.is_logged_in = False

def check_login():
    """检查是否已登录"""
    return st.session_state.is_logged_in

def is_admin():
    """检查当前用户是否为管理员"""
    return st.session_state.teacher_role == 'admin'

def has_class_permission(class_name):
    """检查是否有班级权限"""
    if is_admin():
        return True
    return class_name in st.session_state.teacher_classes

def get_accessible_classes():
    """获取可访问的班级列表"""
    if is_admin():
        # 管理员可以访问所有班级
        all_classes = db.get_classes()
        return [c['class_name'] for c in all_classes]
    return st.session_state.teacher_classes

def show_login_page():
    """显示登录页面 - 全屏沉浸式AI科技风格"""
    # 页面整体样式 - 修改Streamlit原生组件样式
    st.markdown("""
    <style>
    .stApp {
        background: radial-gradient(ellipse at 20% 50%, rgba(99,102,241,0.08) 0%, transparent 50%),
            radial-gradient(ellipse at 80% 50%, rgba(139,92,246,0.08) 0%, transparent 50%),
            radial-gradient(ellipse at 50% 100%, rgba(168,85,247,0.05) 0%, transparent 50%),
            linear-gradient(180deg, #070a1f 0%, #0d1033 40%, #12153d 70%, #0a0e27 100%) !important;
        background-attachment: fixed !important;
    }
    .stTextInput > div > div > input {
        background-color: rgba(255,255,255,0.97) !important;
        border-radius: 12px !important;
        border: 2px solid rgba(99,102,241,0.3) !important;
        font-size: 15px !important;
        padding: 12px 16px !important;
    }
    .stButton > button {
        background: linear-gradient(90deg, #6366f1, #8b5cf6, #a855f7) !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
        letter-spacing: 3px !important;
        font-size: 16px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # 使用 st.html() 渲染装饰性内容（绕过markdown解析器，避免文本化问题）
    bg_html = '''<div style="position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:0;overflow:hidden;">
<svg width="100%" height="100%" style="position:absolute;opacity:0.04;">
<defs><pattern id="hex" width="60" height="104" patternUnits="userSpaceOnUse">
<path d="M30 0 L60 17.3 L60 52 L30 69.3 L0 52 L0 17.3 Z" fill="none" stroke="#6366f1" stroke-width="1"/>
</pattern></defs>
<rect width="100%" height="100%" fill="url(#hex)"/>
</svg>
<div style="position:absolute;top:8%;left:5%;font-size:64px;color:rgba(99,102,241,0.12);font-weight:900;">H</div>
<div style="position:absolute;top:15%;right:8%;font-size:48px;color:rgba(139,92,246,0.1);font-weight:900;">C</div>
<div style="position:absolute;top:35%;left:3%;font-size:56px;color:rgba(168,85,247,0.09);font-weight:900;">O</div>
<div style="position:absolute;top:60%;right:5%;font-size:52px;color:rgba(99,102,241,0.1);font-weight:900;">N</div>
<div style="position:absolute;top:75%;left:8%;font-size:44px;color:rgba(139,92,246,0.08);font-weight:900;">Na</div>
<div style="position:absolute;top:85%;right:12%;font-size:40px;color:rgba(168,85,247,0.1);font-weight:900;">Cl</div>
<div style="position:absolute;top:45%;left:12%;font-size:36px;color:rgba(99,102,241,0.07);font-weight:900;">Fe</div>
<div style="position:absolute;top:25%;right:15%;font-size:42px;color:rgba(139,92,246,0.08);font-weight:900;">S</div>
<svg style="position:absolute;top:20%;left:15%;opacity:0.06;" width="120" height="120" viewBox="0 0 120 120">
<circle cx="60" cy="60" r="20" fill="#6366f1"/><circle cx="30" cy="30" r="12" fill="#8b5cf6"/>
<circle cx="90" cy="30" r="12" fill="#a855f7"/><circle cx="30" cy="90" r="12" fill="#8b5cf6"/>
<circle cx="90" cy="90" r="12" fill="#a855f7"/>
<line x1="48" y1="48" x2="38" y2="38" stroke="#6366f1" stroke-width="2"/>
<line x1="72" y1="48" x2="82" y2="38" stroke="#6366f1" stroke-width="2"/>
<line x1="48" y1="72" x2="38" y2="82" stroke="#6366f1" stroke-width="2"/>
<line x1="72" y1="72" x2="82" y2="82" stroke="#6366f1" stroke-width="2"/>
</svg>
<svg style="position:absolute;bottom:25%;right:18%;opacity:0.05;" width="100" height="100" viewBox="0 0 100 100">
<circle cx="50" cy="50" r="18" fill="#6366f1"/><circle cx="20" cy="50" r="10" fill="#8b5cf6"/>
<circle cx="80" cy="50" r="10" fill="#a855f7"/><circle cx="50" cy="20" r="10" fill="#8b5cf6"/>
<circle cx="50" cy="80" r="10" fill="#a855f7"/>
<line x1="38" y1="50" x2="28" y2="50" stroke="#6366f1" stroke-width="2"/>
<line x1="62" y1="50" x2="72" y2="50" stroke="#6366f1" stroke-width="2"/>
<line x1="50" y1="38" x2="50" y2="28" stroke="#6366f1" stroke-width="2"/>
<line x1="50" y1="62" x2="50" y2="72" stroke="#6366f1" stroke-width="2"/>
</svg>
</div>'''
    st.html(bg_html)

    # 垂直间距
    st.html("<div style='height:6vh;'></div>")

    # 中间列布局
    col1, col2, col3 = st.columns([1, 1.6, 1])
    with col2:
        # 品牌区域 - st.html() 渲染
        brand_html = '''<div style="text-align:center;margin-bottom:35px;position:relative;z-index:1;">
<h1 style="color:#ffffff;font-size:56px;font-weight:900;margin:0 0 8px 0;letter-spacing:12px;text-shadow:0 0 40px rgba(139,92,246,0.6),0 4px 8px rgba(0,0,0,0.3);background:linear-gradient(90deg,#a5b4fc,#c084fc,#f9a8d4,#c084fc,#a5b4fc);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">知错AI</h1>
<p style="color:rgba(255,255,255,0.85);font-size:17px;font-weight:300;margin:0 0 16px 0;letter-spacing:2px;">高中化学错题智能诊断与个性化练习系统</p>
<div style="display:inline-flex;align-items:center;gap:8px;background:rgba(99,102,241,0.15);border:1px solid rgba(139,92,246,0.3);padding:6px 20px;border-radius:30px;margin-bottom:16px;">
<span style="display:inline-block;width:6px;height:6px;background:#34d399;border-radius:50%;"></span>
<span style="color:#a5b4fc;font-size:12px;font-weight:500;letter-spacing:2px;">AI POWERED · INTELLIGENT DIAGNOSIS</span>
</div>
<div style="display:flex;justify-content:center;gap:20px;margin-top:8px;">
<span style="display:inline-block;width:36px;height:36px;background:rgba(99,102,241,0.15);border:1px solid rgba(99,102,241,0.3);border-radius:8px;color:#818cf8;font-size:14px;font-weight:700;line-height:36px;text-align:center;">H</span>
<span style="display:inline-block;width:36px;height:36px;background:rgba(139,92,246,0.15);border:1px solid rgba(139,92,246,0.3);border-radius:8px;color:#c084fc;font-size:14px;font-weight:700;line-height:36px;text-align:center;">C</span>
<span style="display:inline-block;width:36px;height:36px;background:rgba(168,85,247,0.15);border:1px solid rgba(168,85,247,0.3);border-radius:8px;color:#d8b4fe;font-size:14px;font-weight:700;line-height:36px;text-align:center;">O</span>
<span style="display:inline-block;width:36px;height:36px;background:rgba(99,102,241,0.15);border:1px solid rgba(99,102,241,0.3);border-radius:8px;color:#a5b4fc;font-size:14px;font-weight:700;line-height:36px;text-align:center;">N</span>
<span style="display:inline-block;width:36px;height:36px;background:rgba(139,92,246,0.15);border:1px solid rgba(139,92,246,0.3);border-radius:8px;color:#c084fc;font-size:14px;font-weight:700;line-height:36px;text-align:center;">Na</span>
<span style="display:inline-block;width:36px;height:36px;background:rgba(168,85,247,0.15);border:1px solid rgba(168,85,247,0.3);border-radius:8px;color:#d8b4fe;font-size:14px;font-weight:700;line-height:36px;text-align:center;">Cl</span>
</div>
</div>'''
        st.html(brand_html)

        # 登录标题
        st.html('''<div style="text-align:center;margin-bottom:28px;position:relative;z-index:1;">
<span style="font-size:18px;font-weight:600;color:rgba(255,255,255,0.95);letter-spacing:4px;">教师登录</span>
<div style="width:40px;height:2px;background:linear-gradient(90deg,#6366f1,#8b5cf6);margin:10px auto 0;"></div>
</div>''')

        # 输入框
        st.html("<p style='color:#a5b4fc;margin:0 0 6px 0;font-size:14px;letter-spacing:1px;'>👤 账号</p>")
        username = st.text_input("", placeholder="请输入教师账号", label_visibility="collapsed")

        st.html("<p style='color:#a5b4fc;margin:16px 0 6px 0;font-size:14px;letter-spacing:1px;'>🔒 密码</p>")
        password = st.text_input("", type="password", placeholder="请输入密码", label_visibility="collapsed")

        st.html("<div style='height:20px;'></div>")

        if st.button("登 录", type="primary", use_container_width=True):
            if username and password:
                if login_teacher(username, password):
                    st.success(f"欢迎，{st.session_state.teacher_name}！")
                    st.rerun()
                else:
                    st.error("账号或密码错误")
            else:
                st.warning("请输入账号和密码")

        # 底部提示
        st.html("<div style='height:20px;'></div>")
        footer_html = '''<div style="background:rgba(99,102,241,0.08);border:1px solid rgba(139,92,246,0.15);border-radius:14px;padding:18px 24px;text-align:center;position:relative;z-index:1;">
<p style="color:rgba(255,255,255,0.85);font-size:14px;margin:0;line-height:1.8;">
<span style="color:#c084fc;">💡</span>
<b style="color:rgba(255,255,255,0.95);">默认账号：</b><span style="color:#a5b4fc;">admin</span> / <span style="color:#a5b4fc;">admin123</span><br>
<span style="color:rgba(255,255,255,0.5);font-size:13px;">首次登录后请及时修改密码</span>
</p>
</div>'''
        st.html(footer_html)

        # 学校信息
        st.html("<div style='height:16px;'></div>")
        st.html('<div style="text-align:center;color:rgba(255,255,255,0.35);font-size:13px;letter-spacing:1px;position:relative;z-index:1;">🧪 临澧县晟德高级中学 · 化学教研组 🧪</div>')

    st.html("<div style='height:8vh;'></div>")

# ========== 辅助函数 ==========

def export_practice_to_excel(questions, student_answers, filename="练习题目.xlsx"):
    """导出练习题目为Excel格式"""
    import pandas as pd
    from io import BytesIO
    
    data = []
    for i, q in enumerate(questions):
        q_num = i + 1
        question_text = q.get('question_text', '')
        options = q.get('options', [])
        answer = q.get('answer', '')
        explanation = q.get('explanation', '')
        knowledge_point = q.get('knowledge_point', '综合')
        difficulty = q.get('difficulty', 1)
        student_ans = student_answers.get(i, '未作答')
        
        # 处理选项文本
        option_text = '\n'.join([str(opt) for opt in options]) if options else ''
        
        data.append({
            '题号': q_num,
            '题目': question_text,
            '选项': option_text,
            '正确答案': answer,
            '学生答案': student_ans,
            '知识点': knowledge_point,
            '难度': '⭐' * difficulty,
            '解析': explanation
        })
    
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='练习题目', index=False)
        
        # 调整列宽
        worksheet = writer.sheets['练习题目']
        worksheet.column_dimensions['A'].width = 6
        worksheet.column_dimensions['B'].width = 50
        worksheet.column_dimensions['C'].width = 40
        worksheet.column_dimensions['D'].width = 10
        worksheet.column_dimensions['E'].width = 10
        worksheet.column_dimensions['F'].width = 20
        worksheet.column_dimensions['G'].width = 10
        worksheet.column_dimensions['H'].width = 50
    
    output.seek(0)
    return output.getvalue()

def export_practice_to_text(questions, student_answers, filename="练习题目.txt"):
    """导出练习题目为纯文本格式"""
    lines = []
    lines.append("=" * 60)
    lines.append("知错AI - 高中化学错题智能诊断与个性化练习系统")
    lines.append("=" * 60)
    lines.append("")
    
    for i, q in enumerate(questions):
        q_num = i + 1
        question_text = q.get('question_text', '')
        options = q.get('options', [])
        answer = q.get('answer', '')
        explanation = q.get('explanation', '')
        knowledge_point = q.get('knowledge_point', '综合')
        difficulty = q.get('difficulty', 1)
        student_ans = student_answers.get(i, '未作答')
        
        lines.append(f"【第{q_num}题】（{knowledge_point} | 难度{'⭐' * difficulty}）")
        lines.append(f"题目：{question_text}")
        lines.append("")
        
        if options:
            for opt in options:
                lines.append(f"  {opt}")
            lines.append("")
        
        lines.append(f"【正确答案】{answer}")
        lines.append(f"【学生答案】{student_ans}")
        lines.append("")
        
        if explanation:
            lines.append(f"【解析】{explanation}")
            lines.append("")
        
        lines.append("-" * 60)
        lines.append("")
    
    return '\n'.join(lines).encode('utf-8')

def show_export_buttons(questions, student_name="", key_prefix="gen"):
    """显示导出按钮组（生成题目后即可导出）"""
    st.markdown("---")
    st.markdown("### 📤 导出 / 打印练习题目")
    st.caption("下载题目用于打印或线下练习，学生也可以选择在线答题")

    ec1, ec2, ec3 = st.columns(3)

    with ec1:
        if st.button("📊 导出Excel", key=f"export_excel_{key_prefix}", use_container_width=True):
            try:
                excel_data = export_practice_to_excel(questions, {})
                st.download_button(
                    label="⬇️ 下载Excel文件",
                    data=excel_data,
                    file_name=f"知错AI_练习题目{student_name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"导出Excel失败: {str(e)}")

    with ec2:
        if st.button("📝 导出完整版（含答案）", key=f"export_text_{key_prefix}", use_container_width=True):
            try:
                text_data = export_practice_to_text(questions, {})
                st.download_button(
                    label="⬇️ 下载文本文件",
                    data=text_data,
                    file_name=f"知错AI_练习题目{student_name}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"导出文本失败: {str(e)}")

    with ec3:
        if st.button("🖨️ 打印版（无答案）", key=f"export_print_{key_prefix}", use_container_width=True):
            try:
                print_lines = []
                print_lines.append("=" * 60)
                print_lines.append("知错AI - 高中化学错题智能诊断与个性化练习系统")
                print_lines.append("打印练习卷（请独立完成）")
                print_lines.append("=" * 60)
                print_lines.append("")
                print_lines.append("姓名：__________    班级：__________    日期：__________")
                print_lines.append("")

                for i, q in enumerate(questions):
                    q_num = i + 1
                    question_text = q.get('question_text', '')
                    options = q.get('options', [])
                    knowledge_point = q.get('knowledge_point', '综合')
                    difficulty = q.get('difficulty', 1)

                    print_lines.append(f"【第{q_num}题】（{knowledge_point} | 难度{'⭐' * difficulty}）")
                    print_lines.append(f"题目：{question_text}")
                    print_lines.append("")

                    if options:
                        for opt in options:
                            print_lines.append(f"  {opt}")
                        print_lines.append("")

                    print_lines.append("你的答案：__________")
                    print_lines.append("")
                    print_lines.append("-" * 60)
                    print_lines.append("")

                print_data = '\n'.join(print_lines).encode('utf-8')
                st.download_button(
                    label="⬇️ 下载打印版",
                    data=print_data,
                    file_name=f"知错AI_打印练习卷{student_name}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"生成打印版失败: {str(e)}")

def init_ai_service():
    """初始化AI服务"""
    if st.session_state.ai_service is None:
        try:
            # 重置全局缓存，确保读取最新配置
            _ai_module._ai_service = None
            st.session_state.ai_service = get_ai_service()
            # 测试连接
            result = st.session_state.ai_service.test_connection()
            if result["success"]:
                st.success(result["message"])
            else:
                st.warning(result["message"])
        except Exception as e:
            st.error(f"AI服务初始化失败: {str(e)}")
            st.info("请检查API配置或网络连接")
    return st.session_state.ai_service

def show_student_card(student):
    """显示学生信息卡片"""
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("姓名", student.get("name", ""))
    with col2:
        st.metric("班级", student.get("class_name", ""))
    with col3:
        st.metric("年级", student.get("grade", ""))
    with col4:
        st.metric("学号", student.get("student_id", ""))

def show_diagnosis_result(diagnosis):
    """显示诊断结果"""
    st.markdown("---")
    st.markdown("### 📋 诊断结果")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**错误类型**: {diagnosis.get('error_type', '未知')}")
    with col2:
        st.info(f"**薄弱知识点**: {', '.join(diagnosis.get('knowledge_gaps', []))}")
    
    st.markdown("**详细分析**")
    st.write(diagnosis.get('diagnosis_detail', '暂无分析'))
    
    st.markdown("**改进建议**")
    st.success(diagnosis.get('suggestion', '暂无建议'))

# ========== 登录检查 ==========
if not check_login():
    # 未登录，显示登录页面
    show_login_page()
    st.stop()

# ========== 侧边栏 ==========
with st.sidebar:
    st.title("📚 导航菜单")
    
    # 显示当前登录教师信息
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 20px;
        color: white;
    ">
        <div style="font-size: 14px; opacity: 0.9;">当前用户</div>
        <div style="font-size: 18px; font-weight: bold;">{st.session_state.teacher_name}</div>
        <div style="font-size: 12px; opacity: 0.8;">{"管理员" if is_admin() else "教师"}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # 显示可访问的班级
    accessible_classes = get_accessible_classes()
    if accessible_classes:
        st.markdown(f"**负责班级：** {', '.join(accessible_classes)}")
    
    st.markdown("---")
    
    # 根据角色显示不同的菜单
    if is_admin():
        # 管理员看到所有菜单
        page = st.radio(
            "选择功能",
            ["🏠 首页", "👩‍🎓 学生管理", "📝 错题诊断", "📊 诊断报告", "📚 练习推送", "📦 题库管理", "⚙️ 系统设置", "👨‍🏫 教师管理"],
            label_visibility="collapsed"
        )
    else:
        # 普通教师看不到教师管理
        page = st.radio(
            "选择功能",
            ["🏠 首页", "👩‍🎓 学生管理", "📝 错题诊断", "📊 诊断报告", "📚 练习推送", "📦 题库管理", "⚙️ 系统设置"],
            label_visibility="collapsed"
        )
    
    st.markdown("---")
    
    # 退出登录按钮
    if st.button("🚪 退出登录", use_container_width=True):
        logout_teacher()
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 系统信息")
    st.caption("版本: v1.0.0")
    st.caption("开发: 2026年")
    st.caption("基于AI技术的高中化学错题诊断与个性化练习平台，智能分析薄弱点，精准推送练习题，助力高效学习。")

# ========== 主页面 ==========

# 首页
if page == "🏠 首页":
    # ====== 醒目标题设计 ======
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 40px 30px 30px 30px;
        border-radius: 16px;
        text-align: center;
        margin-bottom: 30px;
        box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);
    ">
        <div style="font-size: 52px; margin-bottom: 10px;">🧪</div>
        <h1 style="
            color: #ffffff;
            font-size: 42px;
            font-weight: 900;
            margin: 0 0 8px 0;
            letter-spacing: 6px;
            text-shadow: 0 4px 8px rgba(0,0,0,0.3);
        ">知错AI</h1>
        <h2 style="
            color: rgba(255,255,255,0.95);
            font-size: 18px;
            font-weight: 400;
            margin: 0 0 12px 0;
            letter-spacing: 1px;
        ">高中化学错题智能诊断与个性化练习系统</h2>
        <p style="
            color: rgba(255,255,255,0.85);
            font-size: 14px;
            margin: 0;
            letter-spacing: 1px;
        ">AI赋能个性化教与学，让每个学生的问题都能及时被看见和都能得到针对性的指导</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 快速统计（根据权限显示）
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # 学生总数：管理员看全部，普通教师看自己班级
        accessible_classes = get_accessible_classes()
        if is_admin():
            students = db.get_students()
        else:
            students = []
            for cls_name in accessible_classes:
                students.extend(db.get_students(class_name=cls_name))
        st.metric("学生总数", len(students))
    
    with col2:
        # 题库数量：合并 questions（手动录入）+ question_bank（AI生成）
        manual_questions = db.get_questions(limit=1000)
        bank_questions = db.get_bank_questions(limit=10000)
        st.metric("题库数量", len(manual_questions) + len(bank_questions))

    with col3:
        # 答题记录：合并 student_answers + practice_history
        if students:
            total_answers = sum(len(db.get_student_answers(s['id'])) for s in students[:50])
            # 补充 practice_history 中的记录
            with db.get_connection() as conn:
                cursor = conn.cursor()
                if is_admin():
                    cursor.execute('SELECT COUNT(*) as cnt FROM practice_history')
                else:
                    student_ids = [s['id'] for s in students[:50]]
                    if student_ids:
                        placeholders = ','.join(['?'] * len(student_ids))
                        cursor.execute(f'SELECT COUNT(*) as cnt FROM practice_history WHERE student_id IN ({placeholders})', student_ids)
                    else:
                        cursor.execute('SELECT 0 as cnt')
                row = cursor.fetchone()
                total_answers += row['cnt'] if row else 0
            st.metric("答题记录", total_answers)
        else:
            st.metric("答题记录", 0)
    
    with col4:
        st.metric("知识点覆盖", len(get_kp()))
    
    st.markdown("---")
    
    # 功能介绍
    st.markdown("### 🎯 系统功能")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        **📝 智能诊断**
        - AI自动分析错因
        - 精准定位知识薄弱点
        - 生成个性化诊断报告
        """)
    
    with col2:
        st.markdown("""
        **📚 个性化练习**
        - 根据薄弱点生成变式题
        - 难度循序渐进
        - 即时反馈与解析
        """)
    
    with col3:
        st.markdown("""
        **📊 数据分析**
        - 班级整体情况分析
        - 学生个体追踪
        - 可视化薄弱图谱
        """)
    
    # 快速开始
    st.markdown("### 🚀 快速开始")
    st.info("""
    **使用流程：**
    1. 在"学生管理"中添加学生信息
    2. 在"错题诊断"中输入学生错题
    3. 查看AI生成的诊断报告
    4. 推送个性化练习题
    """)
    
    # AI服务状态检查
    with st.expander("🔧 AI服务状态"):
        if st.button("测试AI连接"):
            ai = init_ai_service()
            if ai:
                result = ai.test_connection()
                if result["success"]:
                    st.success(result["message"])
                else:
                    st.error(result["message"])

# 学生管理
elif page == "👩‍🎓 学生管理":
    st.title("👩‍🎓 学生管理")
    
    # ========================================
    # 版块一：学生列表
    # ========================================
    st.markdown("#### 📋 学生列表")
    
    # 获取可访问的班级列表（根据权限）
    accessible_classes = get_accessible_classes()
    
    # 获取班级列表（只显示有权限的班级）
    all_classes = db.get_classes()
    classes = [c for c in all_classes if c['class_name'] in accessible_classes]
    
    if is_admin():
        class_options = ["全部班级"] + [c['class_name'] for c in classes]
    else:
        # 普通教师默认显示第一个班级，不提供"全部班级"选项
        class_options = [c['class_name'] for c in classes]
    
    col_filter1, col_filter2 = st.columns([1, 1])
    with col_filter1:
        selected_class = st.selectbox("筛选班级", class_options, key="stu_list_class_filter")
    with col_filter2:
        search_name = st.text_input("搜索学生", placeholder="输入姓名搜索", key="stu_list_search")
    
    if selected_class == "全部班级" and is_admin():
        # 管理员可以查看全部班级的学生
        students = db.get_students()
    else:
        # 普通教师只能查看自己班级的学生
        students = db.get_students(class_name=selected_class)
    
    # 搜索过滤
    if search_name:
        students = [s for s in students if search_name in s['name']]
    
    if students:
        df = pd.DataFrame(students)
        df = df[['name', 'student_id', 'class_name', 'grade']]
        df.columns = ['姓名', '学号', '班级', '年级']
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"共 {len(students)} 名学生")
        
        # 学生操作
        with st.expander("🔧 学生操作（查看/删除）"):
            selected_student_name = st.selectbox("选择学生", [s['name'] for s in students], key="stu_op_select")
            selected_student = next((s for s in students if s['name'] == selected_student_name), None)
            
            if selected_student:
                show_student_card(selected_student)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("查看诊断报告", key="stu_op_report"):
                        st.session_state.current_student = selected_student
                        st.info("请到【诊断报告】页面查看")
                
                with col2:
                    if st.button("查看答题记录", key="stu_op_answers"):
                        answers = db.get_student_answers(selected_student['id'])
                        if answers:
                            st.write(f"共有 {len(answers)} 条答题记录")
                            for ans in answers[:5]:
                                st.write(f"- 题目ID: {ans['question_id']}, 正确: {'✓' if ans['is_correct'] else '✗'}")
                        else:
                            st.info("暂无答题记录")
                
                with col3:
                    if st.button("🗑️ 删除学生", key=f"del_btn_{selected_student['id']}"):
                        st.session_state.delete_confirm_student = selected_student
            
            # 删除确认对话框
            if st.session_state.get('delete_confirm_student'):
                del_student = st.session_state.delete_confirm_student
                st.warning(f"⚠️ 确定要删除学生 **{del_student['name']}**（{del_student['student_id']}）吗？")
                st.caption("删除后该学生的所有诊断记录和答题记录也将被清除，此操作不可撤销。")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("确认删除", type="primary", key="confirm_del_student"):
                        try:
                            db.delete_student(del_student['id'])
                            st.success(f"✅ 已删除学生 {del_student['name']}")
                            st.session_state.delete_confirm_student = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"删除失败: {str(e)}")
                with col_no:
                    if st.button("取消", key="cancel_del_student"):
                        st.session_state.delete_confirm_student = None
                        st.rerun()
    else:
        st.info("暂无学生数据，请在下方添加或导入学生")
    
    st.markdown("---")
    
    # ========================================
    # 版块二：添加与导入学生
    # ========================================
    st.markdown("#### ➕ 添加与导入学生")
    
    # ---- 手动添加学生 ----
    st.markdown("##### 📝 手动添加")
    
    with st.form("add_student_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("姓名 *", placeholder="请输入学生姓名")
            student_id = st.text_input("学号 *", placeholder="请输入学生学号")
        
        with col2:
            class_name = st.text_input("班级 *", placeholder="如：2501班")
            grade = st.selectbox("年级", ["高一", "高二", "高三"])
        
        submitted = st.form_submit_button("添加学生", type="primary")
        
        if submitted:
            if name and student_id and class_name:
                try:
                    student = Student(
                        name=name,
                        student_id=student_id,
                        class_name=class_name,
                        grade=grade
                    )
                    db.add_student(student)
                    db.add_class(class_name, grade)
                    st.success(f"✅ 学生 {name} 添加成功！")
                except Exception as e:
                    st.error(f"添加失败: {str(e)}")
            else:
                st.warning("请填写所有必填项")
    
    st.markdown("---")
    
    # ---- 批量导入学生 ----
    st.markdown("##### 📥 批量导入")
        
        # ---- 步骤1：下载模板 ----
    st.markdown("#### 📥 第一步：下载标准模板")
    st.caption("请先下载模板，按格式填写学生信息后上传")
    
    # 生成模板数据
    template_df = pd.DataFrame({
        "姓名": ["张三", "李四", "王五", "赵六"],
        "学号": ["2501001", "2501002", "2502001", "2401001"],
        "班级": ["2501", "2501", "2502", "2401"]
    })
    
    # 将模板写入内存
    template_buffer = io.BytesIO()
    with pd.ExcelWriter(template_buffer, engine='openpyxl') as writer:
        template_df.to_excel(writer, index=False, sheet_name='学生信息')
        # 调整列宽
        worksheet = writer.sheets['学生信息']
        worksheet.column_dimensions['A'].width = 15
        worksheet.column_dimensions['B'].width = 15
        worksheet.column_dimensions['C'].width = 15
        # 添加说明sheet
        instructions = pd.DataFrame({
            '字段说明': [
                '姓名：必填，学生姓名',
                '学号：必填，唯一标识（建议与班级编号对应）',
                '班级：必填，4位数字编号（前2位为入学年份，后2位为班级序号）',
                '  例如：2501 = 2025级1班 = 高一(1)班',
                '        2502 = 2025级2班 = 高一(2)班',
                '        2401 = 2024级1班 = 高二(1)班',
                '        2402 = 2024级2班 = 高二(2)班',
                '        2301 = 2023级1班 = 高三(1)班',
                '年级由系统根据班级编号自动识别，无需手动填写'
            ]
        })
        instructions.to_excel(writer, index=False, sheet_name='填写说明')
    template_buffer.seek(0)
    
    col_download, col_info = st.columns([1, 2])
    with col_download:
        st.download_button(
            label="📥 下载导入模板 (.xlsx)",
            data=template_buffer,
            file_name="学生导入模板.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
    with col_info:
        st.info("""
        **班级编号规则（4位数字）：**
        - **25xx** → 高一(xx)班（2025级）
        - **24xx** → 高二(xx)班（2024级）
        - **23xx** → 高三(xx)班（2023级）
        
        例如：`2501` = 高一(1)班，`2403` = 高二(3)班
        """)
    
    st.markdown("---")
    
    # ---- 步骤2：上传文件 ----
    st.markdown("#### 📤 第二步：上传填写好的文件")
    
    uploaded_file = st.file_uploader(
        "选择Excel文件",
        type=["xlsx", "xls"],
        help="请上传按模板格式填写的Excel文件"
    )
    
    if uploaded_file is not None:
        try:
            # 读取上传的文件
            import_df = pd.read_excel(uploaded_file, engine='openpyxl')
            
            # 标准化列名（去除空格）
            import_df.columns = import_df.columns.str.strip()
            
            # 检查必要列
            required_columns = ["姓名", "学号", "班级"]
            missing_cols = [col for col in required_columns if col not in import_df.columns]
            
            if missing_cols:
                st.error(f"❌ 模板格式错误！缺少必要列：{', '.join(missing_cols)}")
                st.warning("请确保Excel文件包含以下列：姓名、学号、班级")
            else:
                # 清洗数据：去除空行
                import_df = import_df.dropna(subset=["姓名", "学号", "班级"])
                import_df["姓名"] = import_df["姓名"].astype(str).str.strip()
                import_df["学号"] = import_df["学号"].astype(str).str.strip()
                import_df["班级"] = import_df["班级"].astype(str).str.strip()
                
                # ===== 班级编号自动转换 =====
                def parse_class_code(code):
                    """将4位班级编号转换为班级名称和年级
                    2501 -> ('2501班', '高一')
                    2401 -> ('2401班', '高二')
                    2511 -> ('2511班', '高一')
                    """
                    code = str(code).strip()
                    # 已经是中文格式，直接返回
                    if not code.isdigit():
                        grade = code[:2] if '高一' in code else (code[:2] if '高二' in code else '高一')
                        return code, grade
                    
                    if len(code) == 4 and code.isdigit():
                        year_prefix = int(code[:2])
                        
                        # 根据前缀判断年级
                        if year_prefix >= 26:
                            grade = "高一"
                        elif year_prefix == 25:
                            grade = "高一"
                        elif year_prefix == 24:
                            grade = "高二"
                        elif year_prefix == 23:
                            grade = "高三"
                        else:
                            grade = f"{year_prefix}级"
                        
                        # 班级名称保持原编号格式，如 2511、2501
                        class_name = code
                        return class_name, grade
                    
                    return code, "高一"
                
                # 应用转换
                parsed_results = import_df["班级"].apply(parse_class_code)
                import_df["班级"] = parsed_results.apply(lambda x: x[0])
                import_df["年级"] = parsed_results.apply(lambda x: x[1])
                import_df["年级"] = import_df["年级"].astype(str).str.strip()
                
                # 预览数据
                preview_df = import_df.copy()
                preview_df.columns = ['姓名', '学号', '班级', '年级']
                st.markdown("##### 📋 数据预览")
                st.dataframe(preview_df, use_container_width=True, hide_index=True)
                
                st.markdown(f"共 **{len(import_df)}** 条学生记录")
                
                # 显示统计
                col_stat1, col_stat2 = st.columns(2)
                with col_stat1:
                    class_counts = import_df["班级"].value_counts()
                    st.write("**班级分布：**")
                    for cls, cnt in class_counts.items():
                        st.write(f"  - {cls}：{cnt}人")
                with col_stat2:
                    st.write("**年级分布：**")
                    grade_counts = import_df["年级"].value_counts()
                    for grd, cnt in grade_counts.items():
                        st.write(f"  - {grd}：{cnt}人")
                
                # 确认导入
                st.markdown("---")
                confirm = st.button("✅ 确认导入", type="primary", key="confirm_import")
                
                if confirm:
                    success_count = 0
                    skip_count = 0
                    error_list = []
                    
                    for idx, row in import_df.iterrows():
                        try:
                            student = Student(
                                name=row["姓名"],
                                student_id=row["学号"],
                                class_name=row["班级"],
                                grade=row["年级"]
                            )
                            db.add_student(student)
                            db.add_class(row["班级"], row["年级"])
                            success_count += 1
                        except Exception as e:
                            skip_count += 1
                            error_list.append(f"第{idx+2}行 {row['姓名']}({row['学号']}): {str(e)}")
                    
                    # 显示导入结果
                    if success_count > 0:
                        st.success(f"🎉 导入完成！成功 {success_count} 人")
                    
                    if skip_count > 0:
                        st.warning(f"⚠️ 跳过 {skip_count} 人（学号重复或数据异常）")
                        with st.expander("查看跳过详情"):
                            for err in error_list:
                                st.write(f"- {err}")
                    
                    if success_count == 0 and skip_count > 0:
                        st.error("❌ 全部导入失败，请检查数据格式")
                    
                    # 刷新页面
                    st.rerun()
        
        except Exception as e:
            st.error(f"❌ 文件读取失败：{str(e)}")
            st.info("请确保上传的是 .xlsx 格式的Excel文件")
    
    st.markdown("---")
    
    # ---- 补充说明 ----
    with st.expander("📖 常见问题"):
        st.markdown("""
        **Q: 学号重复了怎么办？**
        > 系统会自动跳过学号重复的学生，不会被导入。您可以在"学生列表"中查看已导入的学生。
        
        **Q: 可以导入多个班级吗？**
        > 可以！在"班级"列填写不同的班级编号即可，如2501、2502、2401，系统会自动识别并创建班级。
        
        **Q: 班级编号怎么填？**
        > 4位数字：前2位为入学年份后2位，后2位为班级序号。如2501=高一(1)班，2401=高二(1)班。
        
        **Q: 支持哪些文件格式？**
        > 目前支持 .xlsx 格式（Excel 2007及以上版本）。
        """)

# 错题诊断
elif page == "📝 错题诊断":
    st.title("📝 错题诊断")
    
    # 初始化AI服务
    ai = init_ai_service()
    
    tab1, tab2, tab3 = st.tabs(["📝 单题诊断", "📊 批量诊断", "📋 诊断历史"])
    
    # ========================================
    # 单题诊断
    # ========================================
    with tab1:
        st.markdown("### 单题诊断")
        st.caption("通过图片识别或手动输入，快速分析学生错题原因")
        
        # ---- 输入方式选择 ----
        input_mode = st.radio(
            "输入方式",
            ["📝 手动输入", "📷 图片识别"],
            horizontal=True,
            help="手动输入：直接填写题目信息\n图片识别：上传作业照片，AI自动识别"
        )
        
        # ---- 获取班级列表用于筛选（根据权限）----
        accessible_classes = get_accessible_classes()
        all_classes = db.get_classes()
        classes = [c for c in all_classes if c['class_name'] in accessible_classes]
        
        if is_admin():
            class_options = ["全部班级"] + [c['class_name'] for c in classes]
        else:
            class_options = [c['class_name'] for c in classes]
        selected_class = st.selectbox("筛选班级", class_options, key="diag_class_filter")
        
        if input_mode == "📝 手动输入":
            # ====== 手动输入模式 ======
            if selected_class == "全部班级" and is_admin():
                students = db.get_students()
            else:
                students = db.get_students(class_name=selected_class)
            
            if not students:
                st.warning("当前班级暂无学生，请先添加或选择其他班级")
            else:
                # 选择学生
                student_options = {f"{s['name']}（{s['class_name']}）": s for s in students}
                selected_student_full = st.selectbox("选择学生 *", list(student_options.keys()))
                selected_student = student_options[selected_student_full]
                
                # 题目输入
                col1, col2 = st.columns(2)
                
                with col1:
                    question_type = st.selectbox(
                        "题目类型",
                        ["单选题", "填空题"],
                        help="选择题目类型，影响诊断分析方式"
                    )
                    
                    question_text = st.text_area(
                        "题目内容 *", 
                        height=120,
                        placeholder="请输入题目内容，例如：\n配平下列方程式：\nFe + O₂ → Fe₂O₃"
                    )
                    
                    knowledge_point = st.selectbox(
                        "所属知识点 *",
                        ["请选择知识点"] + list(get_kp().keys())
                    )
                
                with col2:
                    student_answer = st.text_area(
                        "学生答案 *",
                        height=120,
                        placeholder="请输入学生的错误答案"
                    )
                    
                    correct_answer = st.text_input("正确答案 *", placeholder="请输入正确答案")
                
                if st.button("🔍 开始诊断", type="primary"):
                    if question_text and student_answer and correct_answer and knowledge_point != "请选择知识点":
                        with st.spinner("AI正在分析..."):
                            try:
                                diagnosis = ai.diagnose_error(
                                    question=question_text,
                                    student_answer=student_answer,
                                    correct_answer=correct_answer,
                                    knowledge_point=knowledge_point,
                                    question_type=question_type
                                )
                                
                                # 保存到数据库
                                error_diagnosis = ErrorDiagnosis(
                                    question_id=0,
                                    student_id=selected_student['id'],
                                    error_type=diagnosis.get('error_type_code', 'unknown'),
                                    error_type_name=diagnosis.get('error_type', '未知'),
                                    diagnosis_detail=diagnosis.get('diagnosis_detail', ''),
                                    knowledge_gaps=diagnosis.get('knowledge_gaps', []),
                                    suggestion=diagnosis.get('suggestion', '')
                                )
                                db.add_diagnosis(error_diagnosis)
                                
                                # 显示诊断结果
                                st.success(f"✅ 已为 {selected_student['name']} 完成诊断！")
                                show_diagnosis_result(diagnosis)
                            
                            except Exception as e:
                                st.error(f"诊断失败: {str(e)}")
                    else:
                        st.warning("请填写所有必填项（题目、学生答案、正确答案、知识点）")
        
        else:
            # ====== 图片识别模式 ======
            st.info("📷 上传学生作业照片，AI将自动识别题目和学生答案")
            
            # 选择班级（用于筛选学生）
            if selected_class != "全部班级":
                students_in_class = db.get_students(class_name=selected_class)
            else:
                students_in_class = db.get_students()
            
            if not students_in_class:
                st.warning("当前班级暂无学生，请先添加或选择其他班级")
            else:
                # 选择学生
                student_options = {f"{s['name']}（{s['class_name']}）": s for s in students_in_class}
                selected_student_full = st.selectbox("选择学生 *", list(student_options.keys()))
                selected_student = student_options[selected_student_full]
                
                # 上传图片
                uploaded_image = st.file_uploader(
                    "上传作业/试卷照片 *",
                    type=["jpg", "jpeg", "png", "bmp"],
                    help="支持常见图片格式，建议拍摄清晰的照片"
                )
                
                # 知识点选择
                knowledge_point = st.selectbox(
                    "所属知识点 *",
                    ["请选择知识点"] + list(get_kp().keys()),
                    help="请选择本次诊断涉及的知识点"
                )
                
                if uploaded_image is not None:
                    # 显示上传的图片
                    col_img, col_input = st.columns([1, 1])
                    
                    with col_img:
                        st.markdown("**上传的图片：**")
                        st.image(uploaded_image, use_container_width=True)
                    
                    with col_input:
                        st.markdown("**AI识别结果：**")
                        
                        if st.button("🔍 识别图片", type="primary"):
                            with st.spinner("AI正在识别图片..."):
                                try:
                                    # 读取图片数据
                                    image_data = uploaded_image.read()
                                    
                                    # 调用AI图像识别（通过base64编码）
                                    import base64
                                    image_b64 = base64.b64encode(image_data).decode('utf-8')
                                    
                                    # 构建识别提示词
                                    ocr_prompt = """你是一位专业的高中化学教师。请仔细分析这张学生作业/试卷照片：

1. 识别出题目内容（题目要求）
2. 识别出学生的作答内容
3. 如果是选择题，识别学生选择的选项

请以以下JSON格式返回（必须是有效JSON）：
{
    "question_text": "识别到的题目内容",
    "student_answer": "学生的作答内容",
    "is_choice_question": true/false,
    "choices": ["A选项", "B选项", "C选项", "D选项"],  // 如果是选择题
    "confidence": 0.0-1.0  // 识别置信度
}

如果图片不清晰或无法识别，请返回空内容并说明原因。"""
                                    
                                    # 调用AI服务（传入图片）
                                    ocr_result = ai.chat_with_image(ocr_prompt, image_b64)
                                    
                                    if ocr_result:
                                        # 尝试解析JSON
                                        import json
                                        try:
                                            result_data = json.loads(ocr_result)
                                            st.session_state['ocr_result'] = result_data
                                            st.success("✅ 图片识别成功！请核对识别结果并修改")
                                        except:
                                            st.session_state['ocr_result'] = {
                                                'question_text': ocr_result,
                                                'student_answer': '',
                                                'is_choice_question': False
                                            }
                                            st.success("✅ 图片识别完成，请核对内容")
                                except Exception as e:
                                    st.error(f"识别失败: {str(e)}")
                                    st.info("请确保图片清晰，或尝试手动输入")
                        
                        # 显示识别结果（如果已识别）
                        if 'ocr_result' in st.session_state:
                            result = st.session_state['ocr_result']
                            
                            # 可编辑的识别结果
                            question_text = st.text_area(
                                "识别到的题目",
                                value=result.get('question_text', ''),
                                height=100,
                                key="ocr_question"
                            )
                            
                            student_answer = st.text_area(
                                "识别到的学生答案",
                                value=result.get('student_answer', ''),
                                height=80,
                                key="ocr_answer"
                            )
                            
                            correct_answer = st.text_input(
                                "正确答案（请手动输入）",
                                placeholder="请输入正确答案",
                                key="ocr_correct"
                            )
                            
                            # 开始诊断按钮
                            if st.button("🔍 基于识别结果诊断", type="primary"):
                                if question_text and student_answer and correct_answer and knowledge_point != "请选择知识点":
                                    with st.spinner("AI正在分析..."):
                                        try:
                                            diagnosis = ai.diagnose_error(
                                                question=question_text,
                                                student_answer=student_answer,
                                                correct_answer=correct_answer,
                                                knowledge_point=knowledge_point
                                            )
                                            
                                            # 保存到数据库
                                            error_diagnosis = ErrorDiagnosis(
                                                question_id=0,
                                                student_id=selected_student['id'],
                                                error_type=diagnosis.get('error_type_code', 'unknown'),
                                                error_type_name=diagnosis.get('error_type', '未知'),
                                                diagnosis_detail=diagnosis.get('diagnosis_detail', ''),
                                                knowledge_gaps=diagnosis.get('knowledge_gaps', []),
                                                suggestion=diagnosis.get('suggestion', '')
                                            )
                                            db.add_diagnosis(error_diagnosis)
                                            
                                            # 清除识别缓存
                                            if 'ocr_result' in st.session_state:
                                                del st.session_state['ocr_result']
                                            
                                            st.success(f"✅ 已为 {selected_student['name']} 完成诊断！")
                                            show_diagnosis_result(diagnosis)
                                            
                                        except Exception as e:
                                            st.error(f"诊断失败: {str(e)}")
                                else:
                                    st.warning("请检查：题目、学生答案、正确答案是否都已填写")
                        else:
                            st.info("点击上方「识别图片」按钮开始OCR识别")
    
    # ========================================
    # 批量诊断
    # ========================================
    with tab2:
        st.markdown("### 批量诊断")
        st.caption("导入班级考试成绩，自动分析全班的知识薄弱点")
        
        # ---- 步骤1：下载成绩模板 ----
        st.markdown("#### 📥 第一步：下载成绩导入模板")
        
        col_down, col_desc = st.columns([1, 2])
        
        with col_down:
            # 生成成绩导入模板
            # 获取班级列表
            current_classes = db.get_classes()
            template_students = db.get_students()
            
            if not template_students:
                st.warning("请先在【学生管理】中添加学生")
            else:
                # 创建模板DataFrame
                exam_template = pd.DataFrame({
                    "学号": [s['student_id'] for s in template_students],
                    "姓名": [s['name'] for s in template_students],
                    "班级": [s['class_name'] for s in template_students],
                    "总分": ["" for _ in template_students],
                    "第1题得分": ["" for _ in template_students],
                    "第2题得分": ["" for _ in template_students],
                    "第3题得分": ["" for _ in template_students],
                    "第4题得分": ["" for _ in template_students],
                    "第5题得分": ["" for _ in template_students],
                })
                
                # 添加题目信息区域
                template_buffer = io.BytesIO()
                with pd.ExcelWriter(template_buffer, engine='openpyxl') as writer:
                    # 学生成绩表
                    exam_template.to_excel(writer, index=False, sheet_name='成绩单')
                    ws = writer.sheets['成绩单']
                    ws.column_dimensions['A'].width = 12
                    ws.column_dimensions['B'].width = 10
                    ws.column_dimensions['C'].width = 12
                    ws.column_dimensions['D'].width = 8
                    for col in ['E', 'F', 'G', 'H', 'I']:
                        ws.column_dimensions[col].width = 10
                    
                    # 题目信息表
                    questions_info = pd.DataFrame({
                        "题号": ["第1题", "第2题", "第3题", "第4题", "第5题"],
                        "满分": [6, 6, 10, 10, 8],
                        "知识点": ["物质的量", "氧化还原反应", "离子反应", "元素周期律", "金属及其化合物"],
                        "题目类型": ["计算题", "配平题", "书写题", "推断题", "实验题"]
                    })
                    questions_info.to_excel(writer, index=False, sheet_name='题目信息')
                    
                    for col in ['A', 'B', 'C', 'D']:
                        ws2 = writer.sheets['题目信息']
                        ws2.column_dimensions[col].width = 12
                
                template_buffer.seek(0)
                
                st.download_button(
                    label="📥 下载成绩导入模板",
                    data=template_buffer,
                    file_name="考试成绩导入模板.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
        
        with col_desc:
            st.info("""
            **模板说明：**
            - **成绩单**：填写每位学生的得分（留空表示缺考）
            - **题目信息**：设置每道题的满分和知识点
            - 请根据实际考试情况修改"题目信息"表的知识点
            """)
        
        st.markdown("---")
        
        # ---- 步骤2：上传成绩文件 ----
        st.markdown("#### 📤 第二步：上传填写好的成绩文件")
        
        uploaded_exam = st.file_uploader(
            "选择成绩Excel文件",
            type=["xlsx", "xls"],
            key="exam_uploader"
        )
        
        if uploaded_exam is not None:
            try:
                # 读取成绩单
                score_df = pd.read_excel(uploaded_exam, sheet_name='成绩单', engine='openpyxl')
                score_df.columns = score_df.columns.str.strip()
                
                # 读取题目信息
                try:
                    question_df = pd.read_excel(uploaded_exam, sheet_name='题目信息', engine='openpyxl')
                    question_df.columns = question_df.columns.str.strip()
                except:
                    question_df = None
                
                # 数据预览
                st.markdown("##### 📋 成绩预览")
                st.dataframe(score_df, use_container_width=True, hide_index=True)
                
                # 统计信息
                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                
                valid_scores = score_df.dropna(subset=['总分'])
                with col_stat1:
                    st.metric("参考人数", len(valid_scores))
                with col_stat2:
                    class_avg = valid_scores['总分'].mean() if len(valid_scores) > 0 else 0
                    st.metric("班级均分", f"{class_avg:.1f}")
                with col_stat3:
                    max_score = valid_scores['总分'].max() if len(valid_scores) > 0 else 0
                    st.metric("最高分", f"{max_score:.0f}")
                with col_stat4:
                    min_score = valid_scores['总分'].min() if len(valid_scores) > 0 else 0
                    st.metric("最低分", f"{min_score:.0f}")
                
                # ---- 步骤3：批量诊断分析 ----
                st.markdown("---")
                st.markdown("#### 📊 第三步：批量诊断分析")
                
                if st.button("🔍 开始批量诊断并保存", type="primary"):
                    if question_df is not None and len(question_df) > 0:
                        # 获取得分列（除了学号、姓名、班级、总分）
                        score_cols = [col for col in score_df.columns 
                                      if col not in ['学号', '姓名', '班级', '总分']]
                        
                        # 统计每道题的得分情况
                        question_stats = []
                        
                        for i, col in enumerate(score_cols):
                            q_info = question_df.iloc[i] if i < len(question_df) else {}
                            knowledge_point = q_info.get('知识点', f'第{i+1}题')
                            full_score = q_info.get('满分', '')
                            
                            # 计算得分率
                            valid_scores_q = pd.to_numeric(score_df[col], errors='coerce').dropna()
                            if len(valid_scores_q) > 0:
                                avg_score = valid_scores_q.mean()
                                score_rate = avg_score / float(full_score) if full_score else 0
                            else:
                                avg_score = 0
                                score_rate = 0
                            
                            # 找出低分学生
                            low_score_students = score_df[
                                pd.to_numeric(score_df[col], errors='coerce') < float(full_score) * 0.6
                            ][['姓名', col]].values.tolist() if full_score else []
                            
                            question_stats.append({
                                '题号': col,
                                '知识点': knowledge_point,
                                '满分': full_score,
                                '平均得分': round(avg_score, 1),
                                '得分率': f"{score_rate*100:.0f}%",
                                '低分人数': len(low_score_students),
                                '低分学生': low_score_students[:3]  # 只显示前3个
                            })
                        
                        # 显示题目统计表
                        st.markdown("##### 各题得分统计")
                        stats_df = pd.DataFrame(question_stats)
                        display_cols = ['题号', '知识点', '满分', '平均得分', '得分率', '低分人数']
                        st.dataframe(stats_df[display_cols], use_container_width=True, hide_index=True)
                        
                        # 可视化得分率
                        if question_stats:
                            chart_data = pd.DataFrame({
                                '题目': [s['知识点'] for s in question_stats],
                                '得分率(%)': [float(s['得分率'].replace('%','')) for s in question_stats]
                            })
                            st.bar_chart(chart_data.set_index('题目'))
                        
                        # 知识点薄弱度分析
                        st.markdown("##### 🔍 知识点薄弱度分析")
                        
                        # 按知识点统计
                        knowledge_error_stats = {}
                        for stat in question_stats:
                            kp = stat['知识点']
                            if kp not in knowledge_error_stats:
                                knowledge_error_stats[kp] = {
                                    '出错人数': 0,
                                    '参考人数': len(valid_scores),
                                    '低分人数': 0
                                }
                            knowledge_error_stats[kp]['低分人数'] += stat['低分人数']
                        
                        # 排序并显示
                        sorted_knowledge = sorted(
                            knowledge_error_stats.items(), 
                            key=lambda x: x[1]['低分人数'], 
                            reverse=True
                        )
                        
                        for kp, stats in sorted_knowledge:
                            error_rate = stats['低分人数'] / stats['参考人数'] * 100 if stats['参考人数'] > 0 else 0
                            error_level = "🔴 严重" if error_rate > 40 else ("🟡 关注" if error_rate > 20 else "🟢 正常")
                            
                            with st.expander(f"{kp}：出错率 {error_rate:.0f}% {error_level}"):
                                st.write(f"- 出错人数：{stats['低分人数']}/{stats['参考人数']}人")
                                st.write(f"- 得分率：{(1-error_rate/100)*100:.0f}%")
                                
                                # 建议
                                if error_rate > 40:
                                    st.warning(f"⚠️ {kp}需要重点复习，建议安排专项练习")
                                elif error_rate > 20:
                                    st.info(f"💡 {kp}需要加强练习")
                                else:
                                    st.success(f"✅ {kp}整体掌握良好")
                        
                        # ====== 自动保存批量诊断结果到数据库 ======
                        st.markdown("---")
                        st.markdown("##### 💾 自动保存诊断记录")
                        
                        with st.spinner("正在保存诊断记录到数据库..."):
                            saved_count = 0
                            student_knowledge_map = {}  # 用于汇总每个学生的薄弱知识点
                            
                            for i, col in enumerate(score_cols):
                                q_info = question_df.iloc[i] if i < len(question_df) else {}
                                knowledge_point = q_info.get('知识点', f'第{i+1}题')
                                full_score = q_info.get('满分', '')
                                
                                # 找出这道题低分的学生
                                low_score_df = score_df[
                                    pd.to_numeric(score_df[col], errors='coerce') < float(full_score) * 0.6
                                ]
                                
                                for _, student_row in low_score_df.iterrows():
                                    try:
                                        student_name = student_row['姓名']
                                        student_id_no = str(student_row['学号'])
                                        
                                        # 通过学号匹配学生
                                        matched_students = [s for s in template_students if s['student_id'] == student_id_no]
                                        
                                        if matched_students:
                                            student_db_id = matched_students[0]['id']
                                            student_db_name = matched_students[0]['name']
                                            
                                            # 根据得分率智能判断错误类型
                                            student_score = pd.to_numeric(student_row[col], errors='coerce')
                                            score_rate = student_score / float(full_score) if full_score and pd.notna(student_score) else 0
                                            
                                            if score_rate <= 0:
                                                # 完全不得分 → 知识缺失
                                                err_type = 'knowledge_gap'
                                                err_type_name = '知识缺失'
                                                err_detail = f"{col}（{knowledge_point}）得0分，完全未掌握"
                                                err_suggestion = f"建议从基础开始学习{knowledge_point}，先理解核心概念再做练习"
                                            elif score_rate < 0.3:
                                                # 得分率很低 → 知识缺失或概念混淆
                                                err_type = 'concept_confusion'
                                                err_type_name = '概念混淆'
                                                err_detail = f"{col}（{knowledge_point}）得分率仅{score_rate*100:.0f}%，存在概念理解偏差"
                                                err_suggestion = f"建议重新梳理{knowledge_point}的核心概念，对比易混淆知识点"
                                            elif score_rate < 0.6:
                                                # 得分率较低 → 逻辑推理错误
                                                err_type = 'reasoning_error'
                                                err_type_name = '逻辑推理错误'
                                                err_detail = f"{col}（{knowledge_point}）得分率{score_rate*100:.0f}%，解题思路或推理有误"
                                                err_suggestion = f"建议加强{knowledge_point}的解题思路训练，多做同类题型"
                                            else:
                                                # 接近及格 → 审题不清或计算失误
                                                err_type = 'careless_reading'
                                                err_type_name = '审题不清'
                                                err_detail = f"{col}（{knowledge_point}）得分率{score_rate*100:.0f}%，可能存在审题不仔细的问题"
                                                err_suggestion = f"建议做题时仔细审题，注意{knowledge_point}相关的易错条件"
                                            
                                            # 保存诊断记录
                                            error_diagnosis = ErrorDiagnosis(
                                                question_id=0,
                                                student_id=student_db_id,
                                                error_type=err_type,
                                                error_type_name=err_type_name,
                                                diagnosis_detail=err_detail,
                                                knowledge_gaps=[knowledge_point],
                                                suggestion=err_suggestion
                                            )
                                            db.add_diagnosis(error_diagnosis)
                                            saved_count += 1
                                            
                                            # 汇总该学生的薄弱知识点
                                            if student_db_id not in student_knowledge_map:
                                                student_knowledge_map[student_db_id] = {
                                                    'name': student_db_name,
                                                    'weak_knowledge': {}
                                                }
                                            if knowledge_point not in student_knowledge_map[student_db_id]['weak_knowledge']:
                                                student_knowledge_map[student_db_id]['weak_knowledge'][knowledge_point] = 0
                                            student_knowledge_map[student_db_id]['weak_knowledge'][knowledge_point] += 1
                                            
                                    except Exception as e:
                                        pass
                            
                            st.success(f"✅ 已保存 {saved_count} 条诊断记录到数据库")
                            
                            # 显示每个学生的薄弱知识点汇总
                            if student_knowledge_map:
                                st.markdown("##### 📋 学生薄弱知识点汇总")
                                for student_id, data in student_knowledge_map.items():
                                    student_name = data['name']
                                    weak_kps = data['weak_knowledge']
                                    
                                    with st.expander(f"**{student_name}** - 薄弱知识点"):
                                        for kp, count in sorted(weak_kps.items(), key=lambda x: -x[1]):
                                            level = "🔴" if count >= 3 else ("🟡" if count >= 2 else "🟢")
                                            st.write(f"{level} {kp}（{count}题出错）")
                                
                                st.info("💡 可在【诊断报告】页面查看详细的学生诊断报告")
                    
                    else:
                        st.error("❌ 未找到题目信息表，请确保Excel包含「题目信息」工作表")
            
            except Exception as e:
                st.error(f"❌ 文件读取失败：{str(e)}")
                import traceback
                st.code(traceback.format_exc())
    
    # ========================================
    # 诊断历史记录
    # ========================================
    with tab3:
        st.markdown("### 📋 诊断历史记录")
        st.caption("查看所有历史诊断记录，支持按学生、班级、知识点筛选")
        
        # 筛选条件
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            classes = db.get_classes()
            class_filter_options = ["全部班级"] + [c['class_name'] for c in classes]
            hist_class_filter = st.selectbox("筛选班级", class_filter_options, key="hist_class")
        
        with col_f2:
            students_all = db.get_students()
            if hist_class_filter != "全部班级":
                students_filtered = [s for s in students_all if s['class_name'] == hist_class_filter]
            else:
                students_filtered = students_all
            student_filter_options = ["全部学生"] + [f"{s['name']}（{s['class_name']}）" for s in students_filtered]
            hist_student_filter = st.selectbox("筛选学生", student_filter_options, key="hist_student")
        
        with col_f3:
            knowledge_filter_options = ["全部知识点"] + list(get_kp().keys())
            hist_kp_filter = st.selectbox("筛选知识点", knowledge_filter_options, key="hist_kp")
        
        # 构建查询参数
        query_student_id = None
        query_class_name = None
        query_kp = None
        
        if hist_student_filter != "全部学生":
            matched = [s for s in students_filtered if f"{s['name']}（{s['class_name']}）" == hist_student_filter]
            if matched:
                query_student_id = matched[0]['id']
        elif hist_class_filter != "全部班级":
            query_class_name = hist_class_filter
        
        if hist_kp_filter != "全部知识点":
            query_kp = hist_kp_filter
        
        # 获取诊断记录
        diagnoses = db.get_all_diagnoses(
            student_id=query_student_id,
            class_name=query_class_name,
            knowledge_point=query_kp,
            limit=200
        )
        
        # 统计
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.metric("诊断记录总数", len(diagnoses))
        with col_s2:
            if diagnoses:
                unique_students = len(set(d.get('student_name', '') for d in diagnoses if d.get('student_name')))
                st.metric("涉及学生数", unique_students)
        with col_s3:
            if diagnoses:
                unique_kp = set()
                for d in diagnoses:
                    kp = d.get('knowledge_point', '')
                    if kp:
                        unique_kp.add(kp)
                    for gap in d.get('knowledge_gaps', []):
                        if gap:
                            unique_kp.add(gap)
                st.metric("涉及知识点", len(unique_kp))
        
        # 显示记录列表
        if diagnoses:
            st.markdown("---")
            for i, diag in enumerate(diagnoses):
                student_name = diag.get('student_name', '未知')
                class_name = diag.get('class_name', '')
                kp = diag.get('knowledge_point', '') or ', '.join(diag.get('knowledge_gaps', []))
                error_type = diag.get('error_type_name', '未知')
                diag_time = diag.get('diagnosed_at', '')
                
                title = f"**{student_name}**（{class_name}）- {kp} - {error_type}"
                
                with st.expander(f"{i+1}. {title}"):
                    col_d1, col_d2 = st.columns([4, 1])
                    with col_d1:
                        st.markdown(f"**题目**: {diag.get('question_text', diag.get('diagnosis_detail', 'N/A'))}")
                        st.markdown(f"**错因类型**: {error_type}")
                        st.markdown(f"**详细分析**: {diag.get('diagnosis_detail', 'N/A')}")
                        gaps = diag.get('knowledge_gaps', [])
                        if gaps:
                            st.markdown(f"**薄弱知识点**: {', '.join(gaps)}")
                        st.markdown(f"**改进建议**: {diag.get('suggestion', 'N/A')}")
                        st.caption(f"诊断时间: {diag_time}")
                    with col_d2:
                        diag_id = diag.get('id')
                        if diag_id and st.button("🗑️", key=f"del_diag_{diag_id}", help="删除此记录"):
                            if db.delete_diagnosis(diag_id):
                                st.success("已删除")
                                st.rerun()
        else:
            st.info("暂无诊断记录，请先进行错题诊断")

# 诊断报告
elif page == "📊 诊断报告":
    st.title("📊 诊断报告")
    
    # 获取可访问的班级列表
    accessible_classes = get_accessible_classes()
    
    if is_admin():
        students = db.get_students()
    else:
        # 普通教师只看自己班级的学生
        students = []
        for cls_name in accessible_classes:
            students.extend(db.get_students(class_name=cls_name))
    
    if not students:
        st.warning("请先在【学生管理】中添加学生")
    else:
        # ---- 搜索栏：按姓名和班级搜索 ----
        st.markdown("### 🔍 查找学生")
        
        col_search1, col_search2, col_search3 = st.columns([2, 2, 1])
        
        with col_search1:
            search_name = st.text_input("搜索姓名", placeholder="输入学生姓名关键字...", key="report_search_name")
        
        with col_search2:
            all_classes = db.get_classes()
            classes = [c for c in all_classes if c['class_name'] in accessible_classes]
            if is_admin():
                class_options = ["全部班级"] + [c['class_name'] for c in classes]
            else:
                class_options = [c['class_name'] for c in classes]
            search_class = st.selectbox("筛选班级", class_options, key="report_search_class")
        
        with col_search3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔍 搜索", type="primary"):
                pass  # 搜索逻辑在下方实时生效
        
        # 筛选学生列表
        filtered_students = students
        if search_class != "全部班级":
            filtered_students = [s for s in filtered_students if s['class_name'] == search_class]
        if search_name:
            filtered_students = [s for s in filtered_students if search_name in s['name']]
        
        if not filtered_students:
            st.warning("未找到匹配的学生")
        else:
            st.info(f"找到 {len(filtered_students)} 名学生")
            
            # ---- 学生维度诊断汇总 ----
            st.markdown("---")
            st.markdown("### 📊 学生知识点掌握诊断")
            st.caption("按学生维度汇总各知识点诊断情况，红色标记为薄弱知识点")
            
            # 汇总表
            summary_data = []
            for s in filtered_students:
                kp_summary = db.get_student_knowledge_diagnosis_summary(s['id'])
                if kp_summary:
                    for kp_info in kp_summary:
                        summary_data.append({
                            '姓名': s['name'],
                            '班级': s['class_name'],
                            '知识点': kp_info.get('knowledge_point', '综合'),
                            '诊断次数': kp_info.get('diag_count', 0),
                            '错误类型': kp_info.get('error_types', ''),
                            '最近诊断': kp_info.get('last_diag_date', '')
                        })
            
            if summary_data:
                summary_df = pd.DataFrame(summary_data)
                # 标记薄弱知识点（诊断次数>=3）
                def highlight_weak(val):
                    if isinstance(val, int) and val >= 3:
                        return 'color: #E74C3C; font-weight: bold'
                    return ''
                
                styled_df = summary_df.style.map(highlight_weak, subset=['诊断次数'])
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
                
                # 显示三级核心内容分布（点击展开）
                st.markdown("##### 🔍 知识点详情（点击展开查看三级核心内容）")
                for kp_info in kp_summary:
                    kp_name = kp_info.get('knowledge_point', '综合')
                    diag_count = kp_info.get('diag_count', 0)
                    
                    with st.expander(f"📚 {kp_name}（诊断{diag_count}次）"):
                        # 获取该知识点下的所有诊断记录
                        core_records = db.get_student_core_content_summary(s['id'], kp_name)
                        
                        if core_records:
                            # 从诊断详情中提取核心内容并统计
                            core_counter = {}
                            core_errors = {}
                            for rec in core_records:
                                kg = rec.get('knowledge_gaps', '')
                                detail = rec.get('diagnosis_detail', '')
                                error_type = rec.get('error_type_name', '')
                                
                                # 提取核心内容名称
                                core_name = ''
                                if kg and kg.startswith('['):
                                    try:
                                        gaps = json.loads(kg)
                                        # 取与当前知识点最相关的项
                                        for gap in gaps:
                                            if kp_name in str(gap) or str(gap) in kp_name:
                                                core_name = str(gap)
                                                break
                                        if not core_name and gaps:
                                            core_name = gaps[0]
                                    except:
                                        core_name = kg[:30]
                                elif kg:
                                    core_name = kg
                                elif detail:
                                    # 从诊断详情中提取核心内容
                                    core_name = detail.split('，')[0].split('。')[0][:30]
                                else:
                                    core_name = '综合'
                                
                                if not core_name:
                                    core_name = '综合'
                                
                                core_counter[core_name] = core_counter.get(core_name, 0) + 1
                                if core_name not in core_errors:
                                    core_errors[core_name] = set()
                                core_errors[core_name].add(error_type)
                            
                            if core_counter:
                                core_data = []
                                for core_name, count in sorted(core_counter.items(), key=lambda x: x[1], reverse=True):
                                    core_data.append({
                                        '核心内容': core_name,
                                        '诊断次数': count,
                                        '错误类型': '、'.join(core_errors.get(core_name, set()))
                                    })
                                
                                core_df = pd.DataFrame(core_data)
                                st.dataframe(core_df, use_container_width=True, hide_index=True)
                                
                                # 标记最薄弱的核心内容
                                max_count = core_df['诊断次数'].max()
                                weak_cores = core_df[core_df['诊断次数'] == max_count]['核心内容'].tolist()
                                st.warning(f"⚠️ 最薄弱环节：**{', '.join(weak_cores[:2])}**（建议优先强化）")
                                
                                # 验证总数一致性
                                total_core = core_df['诊断次数'].sum()
                                if total_core != diag_count:
                                    st.caption(f"💡 三级核心内容合计 {total_core} 次 = 二级诊断次数 {diag_count} 次")
                            else:
                                st.info("暂无核心内容细分数据")
                        else:
                            st.info("暂无核心内容细分数据")
            else:
                st.info("暂无诊断数据，请先进行错题诊断")
            
            # ---- 逐个学生显示诊断报告 ----
            st.markdown("---")
            st.markdown("### 📋 学生诊断报告详情")
            
            for student in filtered_students:
                with st.expander(f"**{student['name']}**（{student['class_name']}）", expanded=(len(filtered_students) == 1)):
                    show_student_card(student)
                    
                    # 获取该学生的诊断记录
                    diagnoses = db.get_student_diagnoses(student['id'])
                    
                    if diagnoses:
                        st.markdown(f"共 **{len(diagnoses)}** 条诊断记录")
                        
                        # 错因分布
                        error_counts = {}
                        for d in diagnoses:
                            et = d.get('error_type_name', '未知')
                            error_counts[et] = error_counts.get(et, 0) + 1
                        
                        if error_counts:
                            # 左边小、右边大的布局比例（3:7）
                            col_ec1, col_ec2 = st.columns([3, 7])
                            
                            # 错因分布图表（左侧，较小）
                            with col_ec1:
                                st.markdown("**错因分布：**")
                                try:
                                    import matplotlib
                                    import matplotlib.pyplot as plt
                                    # 重建字体管理器缓存，确保加载最新可用字体（兼容新旧版本matplotlib）
                                    try:
                                        matplotlib.font_manager._rebuild()
                                    except AttributeError:
                                        matplotlib.font_manager.fontManager.__init__()
                                    plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'WenQuanYi Micro Hei', 'DejaVu Sans']
                                    plt.rcParams['axes.unicode_minus'] = False
                                    
                                    fig1, ax1 = plt.subplots(figsize=(3.5, 3.5))
                                    # 使用鲜明的区分颜色
                                    error_colors = ['#4A90D9', '#E74C3C', '#F5A623', '#7ED321', '#9B59B6', '#1ABC9C', '#E67E22', '#34495E']
                                    colors1 = error_colors[:len(error_counts)]
                                    wedges, texts, autotexts = ax1.pie(
                                        error_counts.values(), 
                                        labels=error_counts.keys(),
                                        autopct='%1.1f%%',
                                        colors=colors1,
                                        startangle=90,
                                        textprops={'fontsize': 9}
                                    )
                                    for autotext in autotexts:
                                        autotext.set_fontsize(8)
                                        autotext.set_fontweight('bold')
                                    ax1.set_title('错因类型分布', fontsize=10, pad=8)
                                    st.pyplot(fig1)
                                    plt.close(fig1)
                                except:
                                    chart_data = pd.DataFrame({
                                        '错因类型': list(error_counts.keys()),
                                        '数量': list(error_counts.values())
                                    })
                                    st.bar_chart(chart_data.set_index('错因类型'))
                            
                            # 薄弱知识点图表（右侧，较大）
                            with col_ec2:
                                st.markdown("**薄弱知识点：**")
                                knowledge_counts = {}
                                for d in diagnoses:
                                    for gap in d.get('knowledge_gaps', []):
                                        knowledge_counts[gap] = knowledge_counts.get(gap, 0) + 1
                                
                                if knowledge_counts:
                                    sorted_kc = sorted(knowledge_counts.items(), key=lambda x: -x[1])[:8]
                                    
                                    try:
                                        import matplotlib.pyplot as plt
                                        plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'WenQuanYi Micro Hei', 'DejaVu Sans']
                                        plt.rcParams['axes.unicode_minus'] = False
                                        
                                        kp_names = [k for k, v in sorted_kc]
                                        kp_counts = [v for k, v in sorted_kc]
                                        
                                        fig2, ax2 = plt.subplots(figsize=(7, 5))
                                        
                                        # 按出错次数用不同颜色区分严重程度
                                        kp_colors = []
                                        for cnt in kp_counts:
                                            if cnt >= 3:
                                                kp_colors.append('#E74C3C')   # 红色 - 严重
                                            elif cnt >= 2:
                                                kp_colors.append('#F5A623')   # 橙色 - 中等
                                            else:
                                                kp_colors.append('#4A90D9')   # 蓝色 - 一般
                                        
                                        # 如果所有次数相同，使用多色区分
                                        if len(set(kp_counts)) == 1:
                                            multi_colors = ['#E74C3C', '#4A90D9', '#F5A623', '#7ED321', '#9B59B6', '#1ABC9C', '#E67E22', '#34495E']
                                            kp_colors = multi_colors[:len(kp_names)]
                                        
                                        wedges2, texts2, autotexts2 = ax2.pie(
                                            kp_counts,
                                            labels=None,
                                            autopct='%1.1f%%',
                                            colors=kp_colors,
                                            startangle=90,
                                            pctdistance=0.75,
                                            wedgeprops=dict(width=0.5, edgecolor='white', linewidth=2)
                                        )
                                        for autotext in autotexts2:
                                            autotext.set_fontsize(9)
                                            autotext.set_fontweight('bold')
                                        ax2.set_title('知识点薄弱分布', fontsize=12, pad=12)
                                        
                                        # 图例放在底部，横向排列
                                        ax2.legend(wedges2, kp_names, loc='upper center', 
                                                  bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=9,
                                                  frameon=True, fancybox=True, shadow=True)
                                        
                                        # 中心添加总数
                                        ax2.text(0, 0, f'{sum(kp_counts)}次', ha='center', va='center', 
                                                fontsize=14, fontweight='bold', color='#333')
                                        
                                        st.pyplot(fig2)
                                        plt.close(fig2)
                                    except:
                                        kp_df = pd.DataFrame({
                                            '知识点': [k for k, v in sorted_kc],
                                            '出错次数': [v for k, v in sorted_kc]
                                        })
                                        st.bar_chart(kp_df.set_index('知识点'))
                                    
                                    # 文字说明（带颜色标记）
                                    total_count = sum(v for k, v in sorted_kc)
                                    with st.expander("📋 查看详细"):
                                        for kp, cnt in sorted_kc:
                                            pct = cnt / total_count * 100
                                            if cnt >= 3:
                                                icon = "🔴"
                                            elif cnt >= 2:
                                                icon = "🟠"
                                            else:
                                                icon = "🔵"
                                            st.write(f"{icon} {kp}：{cnt}次（{pct:.1f}%）")
                        
                        # 诊断详情
                        st.markdown("**诊断详情：**")
                        for i, diag in enumerate(diagnoses):
                            with st.expander(f"记录 {i+1} - {diag.get('error_type_name', '未知')}"):
                                st.markdown(f"**题目**: {diag.get('question_text', 'N/A')}")
                                st.markdown(f"**知识点**: {diag.get('knowledge_point', 'N/A')}")
                                st.markdown(f"**错因类型**: {diag.get('error_type_name', '未知')}")
                                st.markdown(f"**详细分析**: {diag.get('diagnosis_detail', 'N/A')}")
                                gaps = diag.get('knowledge_gaps', [])
                                if gaps:
                                    st.markdown(f"**薄弱知识点**: {', '.join(gaps)}")
                                st.markdown(f"**改进建议**: {diag.get('suggestion', 'N/A')}")
                                st.caption(f"诊断时间: {diag.get('diagnosed_at', 'N/A')}")
                    else:
                        st.info("该学生暂无诊断记录")

# 练习推送
elif page == "📚 练习推送":
    st.title("📚 个性化练习")
    
    ai = init_ai_service()
    
    # 初始化会话状态
    if 'practice_questions' not in st.session_state:
        st.session_state.practice_questions = None
    if 'student_answers' not in st.session_state:
        st.session_state.student_answers = {}
    if 'submitted' not in st.session_state:
        st.session_state.submitted = False
    if 'current_question_idx' not in st.session_state:
        st.session_state.current_question_idx = 0
    if 'practice_mode' not in st.session_state:
        st.session_state.practice_mode = "从题库选题"  # 默认题库选题模式
    
    # 获取可访问的班级学生
    accessible_classes = get_accessible_classes()
    if is_admin():
        students = db.get_students()
    else:
        students = []
        for cls_name in accessible_classes:
            students.extend(db.get_students(class_name=cls_name))
    
    if not students:
        st.warning("请先添加学生")
    else:
        student_options = {s['name']: s['id'] for s in students}
        selected_student_name = st.selectbox("选择学生", list(student_options.keys()))
        
        # ========================================
        # 模式选择标签页
        # ========================================
        st.markdown("### 选择练习模式")
        
        tab1, tab2, tab3 = st.tabs(["📚 从题库选题", "🤖 AI生成题目", "🎯 针对诊断出题"])
        
        # ========================================
        # 模式1：从题库选题
        # ========================================
        with tab1:
            st.markdown("#### 📚 从题库中选择练习题")
            st.caption("从已有的题库中选择题目进行练习")
            
            # 筛选条件
            col_filter1, col_filter2, col_filter3 = st.columns(3)
            
            with col_filter1:
                knowledge_options = ["全部知识点"] + list(get_kp().keys())
                target_knowledge = st.selectbox("目标知识点", knowledge_options, key="bank_knowledge")
            
            with col_filter2:
                difficulty_filter = st.selectbox("难度筛选", ["全部", "⭐基础", "⭐⭐简单", "⭐⭐⭐中等", "⭐⭐⭐⭐较难", "⭐⭐⭐⭐⭐困难"], key="bank_difficulty")
                difficulty_map = {"全部": None, "⭐基础": 1, "⭐⭐简单": 2, "⭐⭐⭐中等": 3, "⭐⭐⭐⭐较难": 4, "⭐⭐⭐⭐⭐困难": 5}
                diff_value = difficulty_map.get(difficulty_filter)
            
            with col_filter3:
                practice_count = st.selectbox("练习题数", [3, 5, 8, 10, 15, 20], index=0, key="bank_count")
            
            # 从题库获取题目
            if target_knowledge == "全部知识点":
                target_knowledge = None
            
            bank_questions = db.get_bank_questions(knowledge_point=target_knowledge, difficulty=diff_value, limit=200)
            
            # 统计
            col_stat1, col_stat2 = st.columns(2)
            with col_stat1:
                st.info(f"📦 题库中共有 {len(bank_questions)} 道相关题目")
            
            with col_stat2:
                if bank_questions:
                    avg_diff = sum(q.get('difficulty', 1) for q in bank_questions) / len(bank_questions)
                    st.metric("平均难度", f"{avg_diff:.1f}星")
            
            # 题目预览和选择
            if bank_questions:
                st.markdown("---")
                st.markdown("#### 🎯 预览并选择题目")
                
                # 随机选择题目
                import random
                if len(bank_questions) >= practice_count:
                    selected_questions = random.sample(bank_questions, practice_count)
                else:
                    selected_questions = bank_questions
                    st.warning(f"题库中题目不足{practice_count}道，已选择全部{len(selected_questions)}道")
                
                # 预览题目列表
                preview_expanders = []
                for i, q in enumerate(selected_questions):
                    with st.expander(f"**题目 {i+1}**: {q.get('question_text', '')[:50]}...", expanded=False):
                        st.write(f"**知识点**: {q.get('knowledge_point', '未知')}")
                        diff_stars = "⭐" * q.get('difficulty', 1) + "☆" * (5 - q.get('difficulty', 1))
                        st.write(f"**难度**: {diff_stars}")
                        st.write(f"**类型**: {q.get('question_type', '选择题')}")
                        if q.get('options'):
                            st.write("**选项**:")
                            for opt in q.get('options', []):
                                st.write(f"　　{opt}")
                
                if st.button("✅ 开始练习", type="primary", key="start_bank_practice"):
                    # 转换为统一格式
                    practice_questions = []
                    for q in selected_questions:
                        practice_questions.append({
                            'question_text': q.get('question_text', ''),
                            'options': q.get('options', []),
                            'answer': q.get('answer', ''),
                            'explanation': q.get('explanation', ''),
                            'difficulty': q.get('difficulty', 1),
                            'knowledge_point': q.get('knowledge_point', ''),
                            'bank_id': q.get('id', None)
                        })
                    
                    st.session_state.practice_questions = practice_questions
                    st.session_state.student_answers = {}
                    st.session_state.submitted = False
                    st.session_state.current_question_idx = 0
                    st.session_state.practice_mode = "从题库选题"
                    st.success(f"✅ 已选择 {len(practice_questions)} 道题目！")
                    
                    # 生成后立即提供导出选项
                    st.info("💡 您可以在线答题，也可以导出题目打印给学生练习")
                    show_export_buttons(practice_questions, selected_student_name, "bank")
                    st.rerun()
            else:
                st.warning("题库中没有符合条件的题目，请先使用AI生成题目或调整筛选条件")
                
                # 快速生成按钮
                st.markdown("💡 **提示**: 尝试调整筛选条件，或切换到【AI生成题目】标签页生成新题")
        
        # ========================================
        # 模式2：AI生成题目
        # ========================================
        with tab2:
            st.markdown("#### 🤖 AI生成个性化练习题")
            st.caption("让AI根据设置的条件生成专属练习题")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                ai_knowledge = st.selectbox(
                    "目标知识点",
                    list(get_kp().keys()),
                    key="ai_knowledge"
                )
            
            with col2:
                ai_difficulty = st.slider("练习难度", 1, 5, 2, key="ai_difficulty")
            
            with col3:
                ai_error_type = st.selectbox(
                    "针对错误",
                    ["概念混淆", "计算失误", "审题不清", "知识缺失", "逻辑推理错误", "综合练习"],
                    key="ai_error_type"
                )
            
            ai_count = st.selectbox("生成题数", [3, 5, 8, 10], index=0, key="ai_count")
            
            if st.button("🤖 生成练习题", type="primary", key="generate_ai_practice"):
                with st.spinner("🔮 AI正在生成练习题..."):
                    try:
                        questions = ai.generate_practice_questions(
                            target_knowledge=ai_knowledge,
                            error_type=ai_error_type,
                            difficulty=ai_difficulty,
                            count=ai_count
                        )
                        
                        if questions:
                            # 生成后立即存入题库（确保题库概览能显示）
                            # 一次性查询已有题目，避免循环中重复查询
                            existing_bank = db.get_bank_questions(knowledge_point=ai_knowledge, limit=1000)
                            saved_bank_count = 0
                            for q in questions:
                                q_text = q.get('question_text', '')
                                q_id = None
                                for eq in existing_bank:
                                    if q_text in eq.get('question_text', '') or eq.get('question_text', '') in q_text:
                                        q_id = eq['id']
                                        break
                                
                                if q_id is None:
                                    # 新题目：存入题库，add_question_to_bank返回新ID
                                    q_id = db.add_question_to_bank({
                                        'question_text': q.get('question_text', ''),
                                        'question_type': '选择题' if q.get('options') else '填空题',
                                        'knowledge_point': ai_knowledge,
                                        'difficulty': ai_difficulty,
                                        'answer': q.get('answer', ''),
                                        'options': q.get('options', []),
                                        'explanation': q.get('explanation', '')
                                    })
                                    saved_bank_count += 1
                                # 绑定bank_id，提交答案时直接用
                                q['bank_id'] = q_id
                            
                            # 初始化答题状态
                            st.session_state.practice_questions = questions
                            st.session_state.student_answers = {}
                            st.session_state.submitted = False
                            st.session_state.current_question_idx = 0
                            st.session_state.practice_mode = "AI生成"
                            st.success(f"✅ 生成了 {len(questions)} 道练习题！已自动存入题库({saved_bank_count}道新题)")
                            
                            # 生成后立即提供导出选项
                            st.info("💡 您可以在线答题，也可以导出题目打印给学生练习")
                            show_export_buttons(questions, selected_student_name, "ai")
                        else:
                            st.warning("未能生成练习题，请稍后重试")
                            st.info("💡 可能原因：1) AI服务未配置API Key 2) 网络连接异常 3) API额度不足。请到【系统设置】检查AI配置。")
                    
                    except Exception as e:
                        st.error(f"生成失败: {str(e)}")
        
        # ========================================
        # 模式3：针对诊断出题
        # ========================================
        with tab3:
            st.markdown("#### 🎯 针对诊断薄弱知识点出题")
            st.caption("根据学生的诊断报告，自动识别薄弱知识点并生成针对性练习（LaTeX格式）")
            
            selected_student_id = student_options.get(selected_student_name, 0)
            
            if selected_student_id:
                # 获取该学生的诊断汇总
                kp_summary = db.get_student_knowledge_diagnosis_summary(selected_student_id)
                
                # 获取诊断记录中的薄弱知识点
                diagnoses = db.get_student_diagnoses(selected_student_id)
                weak_knowledge = {}
                for d in diagnoses:
                    for gap in d.get('knowledge_gaps', []):
                        if gap:
                            weak_knowledge[gap] = weak_knowledge.get(gap, 0) + 1
                
                if weak_knowledge:
                    # 按频率排序
                    sorted_weak = sorted(weak_knowledge.items(), key=lambda x: -x[1])
                    
                    st.markdown("##### 📊 薄弱知识点分析")
                    
                    # 显示薄弱知识点
                    weak_cols = st.columns(min(len(sorted_weak), 4))
                    for i, (kp, cnt) in enumerate(sorted_weak[:8]):
                        with weak_cols[i % 4]:
                            level = "🔴 严重" if cnt >= 3 else ("🟡 关注" if cnt >= 2 else "🟢 轻微")
                            st.metric(f"{kp}", f"{cnt}次", delta=level)
                    
                    # 选择要针对练习的知识点
                    st.markdown("##### 🎯 选择练习目标")
                    
                    weak_options = [f"{kp}（诊断{cnt}次）" for kp, cnt in sorted_weak]
                    selected_weak = st.multiselect(
                        "选择要针对练习的薄弱知识点",
                        weak_options,
                        default=[weak_options[0]] if weak_options else [],
                        key="weak_kp_select"
                    )
                    
                    # 提取知识点名称
                    target_kps = []
                    for w in selected_weak:
                        kp_name = w.split('（诊断')[0]
                        target_kps.append(kp_name)
                    
                    if target_kps:
                        st.info(f"已选择 {len(target_kps)} 个知识点：{', '.join(target_kps)}")
                        
                        col_w1, col_w2 = st.columns(2)
                        with col_w1:
                            weak_difficulty = st.slider("练习难度", 1, 5, 2, key="weak_difficulty")
                        with col_w2:
                            weak_count = st.selectbox("每知识点题数", [2, 3, 5], index=0, key="weak_count")
                        
                        if st.button("🎯 生成针对性练习", type="primary", key="gen_weak_practice"):
                            all_questions = []
                            total_count = weak_count * len(target_kps)
                            
                            with st.spinner(f"🔮 AI正在为 {selected_student_name} 生成 {total_count} 道针对性练习题..."):
                                for kp in target_kps:
                                    try:
                                        questions = ai.generate_practice_questions(
                                            target_knowledge=kp,
                                            error_type="综合练习",
                                            difficulty=weak_difficulty,
                                            count=weak_count,
                                            use_latex=True
                                        )
                                        all_questions.extend(questions)
                                    except Exception as e:
                                        st.warning(f"生成 {kp} 题目失败: {str(e)}")
                                
                                if all_questions:
                                    # 生成后立即存入题库（确保题库概览能显示）
                                    # 按知识点分组查询已有题目，减少数据库查询次数
                                    kp_cache = {}
                                    saved_bank_count = 0
                                    for q in all_questions:
                                        kp_name = q.get('knowledge_point', '')
                                        # 缓存每个知识点的已有题目
                                        if kp_name not in kp_cache:
                                            kp_cache[kp_name] = db.get_bank_questions(knowledge_point=kp_name, limit=1000)
                                        existing = kp_cache[kp_name]
                                        
                                        q_id = None
                                        q_text = q.get('question_text', '')
                                        for eq in existing:
                                            if q_text in eq.get('question_text', '') or eq.get('question_text', '') in q_text:
                                                q_id = eq['id']
                                                break
                                        
                                        if q_id is None:
                                            q_id = db.add_question_to_bank({
                                                'question_text': q.get('question_text', ''),
                                                'question_type': '选择题' if q.get('options') else '填空题',
                                                'knowledge_point': kp_name,
                                                'difficulty': weak_difficulty,
                                                'answer': q.get('answer', ''),
                                                'options': q.get('options', []),
                                                'explanation': q.get('explanation', '')
                                            })
                                            saved_bank_count += 1
                                        # 绑定bank_id
                                        q['bank_id'] = q_id
                                    
                                    st.session_state.practice_questions = all_questions
                                    st.session_state.student_answers = {}
                                    st.session_state.submitted = False
                                    st.session_state.current_question_idx = 0
                                    st.session_state.practice_mode = "针对诊断"
                                    st.success(f"✅ 生成了 {len(all_questions)} 道针对性练习题！已自动存入题库({saved_bank_count}道新题)")
                                    
                                    # 生成后立即提供导出选项
                                    st.info("💡 您可以在线答题，也可以导出题目打印给学生练习")
                                    show_export_buttons(all_questions, selected_student_name, "weak")
                                else:
                                    st.warning("未能生成练习题，请稍后重试")
                    else:
                        st.info("请选择要针对练习的知识点")
                else:
                    st.info(f"学生 {selected_student_name} 暂无诊断记录，无法识别薄弱知识点")
                    st.markdown("💡 请先在【错题诊断】页面为该学生进行诊断")
            else:
                st.warning("请先选择学生")
        
        # ========================================
        # 练习答题界面（多种模式共用）
        # ========================================
        if st.session_state.practice_questions:
            questions = st.session_state.practice_questions
            total_questions = len(questions)
            practice_mode = st.session_state.get('practice_mode', 'AI生成')
            
            # ---- 答题模式切换 ----
            st.markdown("---")
            
            mode_col1, mode_col2, mode_col3 = st.columns([3, 1, 1])
            
            with mode_col1:
                if not st.session_state.submitted:
                    st.markdown("### ✏️ 答题区")
                    mode_label = "📚 题库选题" if practice_mode == "从题库选题" else "🤖 AI生成"
                    st.caption(f"共 {total_questions} 题（{mode_label}），请逐题作答")
                else:
                    st.markdown("### 📊 答题结果")
            
            with mode_col2:
                if st.button("🔄 重新开始", key="restart_quiz"):
                    st.session_state.practice_questions = None
                    st.session_state.student_answers = {}
                    st.session_state.submitted = False
                    st.session_state.current_question_idx = 0
                    st.rerun()
            
            # ---- 答题进度 ----
            if not st.session_state.submitted:
                progress_cols = st.columns(total_questions)
                for i in range(total_questions):
                    with progress_cols[i]:
                        if i in st.session_state.student_answers:
                            st.markdown(f"**题{i+1}：** ✅")
                        else:
                            st.markdown(f"**题{i+1}：** ⬜")
            
            # ---- 逐题显示 ----
            for i, q in enumerate(questions):
                q_num = i + 1
                question_text = q.get('question_text', '')
                options = q.get('options', [])
                answer = q.get('answer', '')
                explanation = q.get('explanation', '')
                difficulty_val = q.get('difficulty', 1)
                
                # 标准化答案（去除空格、转小写）
                correct_answer_normalized = str(answer).strip().upper()
                
                # 判断是否为选择题
                is_choice = len(options) >= 2 and not question_text.startswith('计算')
                is_submitted = st.session_state.submitted
                
                # ---- 选择题 ----
                if is_choice:
                    # 提取选项列表（支持多种格式）
                    option_list = []
                    option_texts = []  # 纯文本选项内容（不含A/B/C/D前缀）
                    for opt in options:
                        opt_str = str(opt).strip()
                        if opt_str.startswith(('A', 'B', 'C', 'D')) or opt_str.startswith(('a', 'b', 'c', 'd')):
                            # 提取选项内容（去掉A. B.等前缀）
                            opt_content = opt_str[2:].strip() if len(opt_str) > 2 and opt_str[1] in '.、 ' else opt_str
                            option_list.append(opt_str)
                            option_texts.append(opt_content)
                        elif len(option_list) < 4:
                            # 自动添加ABCD
                            prefix = ['A', 'B', 'C', 'D'][len(option_list)]
                            option_list.append(f"{prefix}. {opt_str}")
                            option_texts.append(opt_str)
                    
                    st.markdown("---")
                    # 渲染题目（支持LaTeX化学式）
                    render_latex_text(question_text, q_num)
                    
                    # 渲染选项（支持LaTeX化学式，合并为一个HTML块，用iframe+KaTeX渲染）
                    all_options_html = '<div style="margin:2px 0;">'
                    for idx, opt_text in enumerate(option_texts):
                        letter = ['A', 'B', 'C', 'D'][idx]
                        all_options_html += '<div style="margin:1px 0;">' + f"<b>{letter}.</b> {opt_text}" + '</div>'
                    all_options_html += '</div>'
                    render_latex_html(all_options_html, font_size="16px", line_height="1.7")
                    
                    # 难度星级
                    diff_stars = "⭐" * difficulty_val + "☆" * (5 - difficulty_val)
                    st.caption(f"难度：{diff_stars}")
                    
                    if not is_submitted:
                        # 未提交时：学生选择答案
                        answer_key = f"q_{i}_answer"
                        
                        selected = st.radio(
                            "请选择答案：",
                            options=["A", "B", "C", "D"][:len(option_list)],
                            key=answer_key,
                            horizontal=True
                        )
                        
                        # 显示当前选中选项的完整内容（支持LaTeX）
                        selected_idx = ["A", "B", "C", "D"].index(selected)
                        render_latex_html(f'<span style="color:#0066cc;">已选择：{selected}. {option_texts[selected_idx]}</span>', font_size="15px")
                        
                        if st.button(f"✅ 确认第{q_num}题", key=f"confirm_{i}"):
                            st.session_state.student_answers[i] = selected
                            st.rerun()
                        
                        # 显示已选答案
                        if i in st.session_state.student_answers:
                            letters = ['A', 'B', 'C', 'D']
                            selected_idx = letters[:len(option_list)].index(st.session_state.student_answers[i])
                            render_latex_html(f"已确认选择：{option_list[selected_idx]}", font_size="15px")
                    else:
                        # 已提交：显示答案判断
                        student_ans = st.session_state.student_answers.get(i)
                        
                        if student_ans:
                            student_opt_idx = ["A", "B", "C", "D"][:len(option_list)].index(student_ans)
                            student_opt_text = option_texts[student_opt_idx]
                            
                            correct_idx = ["A", "B", "C", "D"][:len(option_list)].index(correct_answer_normalized) if correct_answer_normalized in ["A","B","C","D"] else 0
                            correct_opt_text = option_texts[correct_idx]
                            
                            if student_ans == correct_answer_normalized:
                                render_latex_html(f'<span style="color:green;">✅ 回答正确！你的答案：{student_ans}. {student_opt_text}</span>', font_size="15px")
                            else:
                                render_latex_html(f'<span style="color:red;">❌ 回答错误！你的答案：{student_ans}. {student_opt_text}</span>', font_size="15px")
                                render_latex_html(f'<span style="color:blue;">✅ 正确答案：{correct_answer_normalized}. {correct_opt_text}</span>', font_size="15px")
                        else:
                            st.warning("⏭️ 未作答")
                            correct_idx = ["A", "B", "C", "D"][:len(option_list)].index(correct_answer_normalized) if correct_answer_normalized in ["A","B","C","D"] else 0
                            correct_opt_text = option_texts[correct_idx]
                            render_latex_html(f"✅ 正确答案：{correct_answer_normalized}. {correct_opt_text}", font_size="15px")
                
                # ---- 非选择题（计算、简答等）----
                else:
                    st.markdown("---")
                    # 渲染题目（支持LaTeX）
                    render_latex_text(question_text, q_num)
                    
                    # 难度星级
                    diff_stars = "⭐" * difficulty_val + "☆" * (5 - difficulty_val)
                    st.caption(f"难度：{diff_stars}")
                    
                    if not is_submitted:
                        # 学生输入答案
                        answer_key = f"q_{i}_text_answer"
                        student_input = st.text_input(
                            "请输入你的答案：",
                            key=answer_key,
                            placeholder="在此输入答案..."
                        )
                        
                        if st.button(f"✅ 确认第{q_num}题", key=f"confirm_{i}"):
                            if student_input.strip():
                                st.session_state.student_answers[i] = student_input.strip()
                                st.rerun()
                            else:
                                st.warning("请先输入答案")
                        
                        if i in st.session_state.student_answers:
                            st.success(f"已提交：{st.session_state.student_answers[i]}")
                    else:
                        # 显示答案
                        student_ans = st.session_state.student_answers.get(i)
                        
                        if student_ans:
                            if student_ans.upper() == correct_answer_normalized.upper():
                                st.success(f"✅ 回答正确！你的答案：{student_ans}")
                            else:
                                st.warning(f"你的答案：{student_ans}")
                                st.info(f"✅ 正确答案：{answer}")
                        else:
                            st.warning("⏭️ 未作答")
                            st.info(f"✅ 正确答案：{answer}")
                
                # ---- 显示解析 ----
                if is_submitted and explanation:
                    with st.expander("📖 查看解析"):
                        # 处理解析文本，让每个选项（A选项、B选项、C选项、D选项）单独一行
                        import re
                        formatted_explanation = explanation
                        # 在 "A选项"、"B选项"、"C选项"、"D选项" 前添加换行
                        formatted_explanation = re.sub(r'(A选项)', r'<br>\1', formatted_explanation)
                        formatted_explanation = re.sub(r'(B选项)', r'<br>\1', formatted_explanation)
                        formatted_explanation = re.sub(r'(C选项)', r'<br>\1', formatted_explanation)
                        formatted_explanation = re.sub(r'(D选项)', r'<br>\1', formatted_explanation)
                        # 移除可能产生的多余换行
                        formatted_explanation = formatted_explanation.replace('<br><br>', '<br>')
                        render_latex_html(formatted_explanation, font_size="16px", line_height="1.8")
            
            # ---- 提交试卷按钮 ----
            st.markdown("---")
            
            if not st.session_state.submitted:
                answered_count = len(st.session_state.student_answers)
                
                if answered_count < total_questions:
                    st.warning(f"⚠️ 已作答 {answered_count}/{total_questions} 题，还有 {total_questions - answered_count} 题未作答")
                
                if st.button("📤 提交试卷", type="primary", disabled=(answered_count == 0)):
                    st.session_state.submitted = True
                    st.rerun()
            
            # ---- 答题结果统计 ----
            if st.session_state.submitted:
                correct_count = 0
                for i, q in enumerate(questions):
                    answer = q.get('answer', '')
                    answer_normalized = str(answer).strip().upper()
                    student_ans = st.session_state.student_answers.get(i)
                    
                    if student_ans:
                        if answer_normalized in ["A","B","C","D"]:
                            if student_ans.upper() == answer_normalized:
                                correct_count += 1
                        elif student_ans.upper().strip() == answer_normalized.upper().strip():
                            correct_count += 1
                
                accuracy = correct_count / total_questions * 100
                
                # 结果统计卡片
                col_res1, col_res2, col_res3, col_res4 = st.columns(4)
                
                with col_res1:
                    st.metric("总题数", total_questions)
                with col_res2:
                    st.metric("已作答", len(st.session_state.student_answers))
                with col_res3:
                    st.metric("正确", correct_count)
                with col_res4:
                    st.metric("正确率", f"{accuracy:.0f}%")
                
                # 保存练习记录到数据库
                selected_student_id = student_options.get(selected_student_name, 0)
                
                # 统计保存
                saved_count = 0
                for i, q in enumerate(questions):
                    answer = q.get('answer', '')
                    answer_normalized = str(answer).strip().upper()
                    student_ans = st.session_state.student_answers.get(i)
                    difficulty_val = q.get('difficulty', 1)
                    knowledge_point = q.get('knowledge_point', '综合')
                    
                    if student_ans and selected_student_id:
                        # 判断对错
                        is_correct = False
                        if answer_normalized in ["A","B","C","D"]:
                            is_correct = student_ans.upper() == answer_normalized
                        else:
                            is_correct = student_ans.upper().strip() == answer_normalized.upper().strip()
                        
                        # 题库选题模式：使用bank_id直接保存
                        bank_id = q.get('bank_id')
                        
                        if bank_id:
                            # 直接使用题库中的题目ID（包括AI生成已存入题库的）
                            db.add_practice_record(
                                student_id=selected_student_id,
                                question_id=bank_id,
                                student_answer=student_ans,
                                is_correct=is_correct,
                                difficulty_level=difficulty_val
                            )
                            saved_count += 1
                        else:
                            # 兜底：如果没有bank_id，先存入题库再保存记录
                            existing_questions = db.get_bank_questions(
                                knowledge_point=knowledge_point,
                                limit=1000
                            )
                            q_id = None
                            q_text = q.get('question_text', '')
                            for eq in existing_questions:
                                if q_text in eq.get('question_text', '') or eq.get('question_text', '') in q_text:
                                    q_id = eq['id']
                                    break
                            
                            if q_id is None:
                                q_id = db.add_question_to_bank({
                                    'question_text': q.get('question_text', ''),
                                    'question_type': '选择题' if q.get('options') else '填空题',
                                    'knowledge_point': knowledge_point,
                                    'difficulty': difficulty_val,
                                    'answer': answer,
                                    'options': q.get('options', []),
                                    'explanation': q.get('explanation', '')
                                })
                            
                            db.add_practice_record(
                                student_id=selected_student_id,
                                question_id=q_id,
                                student_answer=student_ans,
                                is_correct=is_correct,
                                difficulty_level=difficulty_val
                            )
                            saved_count += 1
                
                if saved_count > 0:
                    st.success(f"📝 已保存 {saved_count} 条练习记录！")
                
                # 结果评价
                if accuracy >= 90:
                    st.success("🎉 太棒了！正确率90%以上，继续保持！")
                elif accuracy >= 70:
                    st.info("👍 不错！正确率70%以上，再接再厉！")
                elif accuracy >= 50:
                    st.warning("💪 加油！正确率50%以上，需要加强练习")
                else:
                    st.error("📚 建议重新学习相关知识点后再次练习")
                
                # 薄弱知识点提示
                weak_knowledge = []
                for i, q in enumerate(questions):
                    answer = q.get('answer', '')
                    answer_normalized = str(answer).strip().upper()
                    student_ans = st.session_state.student_answers.get(i)
                    
                    if student_ans:
                        is_wrong = True
                        if answer_normalized in ["A","B","C","D"]:
                            is_wrong = student_ans.upper() != answer_normalized
                        else:
                            is_wrong = student_ans.upper().strip() != answer_normalized.upper().strip()
                        
                        if is_wrong:
                            weak_knowledge.append(q.get('knowledge_point', '综合'))
                
                if weak_knowledge:
                    st.markdown("### 📋 薄弱知识点")
                    
                    # 统计薄弱知识点出现次数
                    from collections import Counter
                    weak_counts = Counter(weak_knowledge)
                    
                    for kp, cnt in weak_counts.most_common():
                        with st.expander(f"🔴 {kp}（出错 {cnt} 次）"):
                            st.write("建议在系统中针对此知识点进行专项诊断和练习")
                
                # ---- 导出练习题目 ----
                show_export_buttons(questions, selected_student_name, "result")

# ========================================
# 题库管理
# ========================================
elif page == "📦 题库管理":
    st.title("📦 题库管理")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📚 题库概览", "📝 AI生成题目", "📖 练习记录", "📊 掌握统计", "📥 手动上传"])
    
    # ---- 标签1：题库概览 ----
    with tab1:
        st.markdown("### 📚 AI生成题库概览")
        st.caption("查看已生成的题目，按知识点分类管理")
        
        # 知识点筛选
        knowledge_options = ["全部知识点"] + list(get_kp().keys())
        selected_knowledge = st.selectbox("按知识点筛选", knowledge_options)
        
        # 难度筛选
        difficulty_filter = st.selectbox("按难度筛选", ["全部难度", "⭐基础", "⭐⭐简单", "⭐⭐⭐中等", "⭐⭐⭐⭐较难", "⭐⭐⭐⭐⭐困难"])
        difficulty_map = {"全部难度": None, "⭐基础": 1, "⭐⭐简单": 2, "⭐⭐⭐中等": 3, "⭐⭐⭐⭐较难": 4, "⭐⭐⭐⭐⭐困难": 5}
        diff_value = difficulty_map.get(difficulty_filter)
        
        # 获取题目列表
        if selected_knowledge == "全部知识点":
            selected_knowledge = None
        
        questions = db.get_bank_questions(knowledge_point=selected_knowledge, difficulty=diff_value, limit=200)
        
        # 统计信息
        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
        
        with col_stat1:
            st.metric("题目总数", len(questions))
        
        with col_stat2:
            kp_counts = {}
            for q in questions:
                kp = q.get('knowledge_point', '未知')
                kp_counts[kp] = kp_counts.get(kp, 0) + 1
            st.metric("知识点数", len(kp_counts))
        
        with col_stat3:
            total_used = sum(q.get('times_used', 0) for q in questions)
            st.metric("练习人次", total_used)
        
        with col_stat4:
            total_correct = sum(q.get('times_correct', 0) for q in questions)
            accuracy = total_correct / total_used * 100 if total_used > 0 else 0
            st.metric("正确率", f"{accuracy:.0f}%")
        
        # 知识点分布
        if questions:
            st.markdown("#### 知识点分布")
            kp_data = {}
            for q in questions:
                kp = q.get('knowledge_point', '未知')
                kp_data[kp] = kp_data.get(kp, 0) + 1
            
            kp_df = pd.DataFrame({
                '知识点': list(kp_data.keys()),
                '题目数': list(kp_data.values())
            })
            st.bar_chart(kp_df.set_index('知识点'))
        
        # 题目列表
        st.markdown("#### 题目列表")
        
        if questions:
            # 展示题目
            for i, q in enumerate(questions):
                difficulty_val = q.get('difficulty', 1)
                diff_stars = "⭐" * difficulty_val + "☆" * (5 - difficulty_val)
                
                with st.expander(f"第{i+1}题 [{q.get('knowledge_point', '未知')} {diff_stars}] - 练习{int(q.get('times_used', 0))}次 - {q.get('times_correct', 0)}正确"):
                    st.markdown(f"**题目类型：** {q.get('question_type', '选择题')}")
                    st.markdown("**题目内容：**")
                    render_latex_html(q.get('question_text', ''), font_size="16px")
                    
                    if q.get('options'):
                        st.markdown("**选项：**")
                        all_opts = '<div style="margin:2px 0;">'
                        for idx, opt in enumerate(q.get('options', [])):
                            letter = ['A', 'B', 'C', 'D'][idx]
                            opt_str = str(opt).strip()
                            # 如果选项已经有A. B.前缀则去掉
                            if opt_str and opt_str[0] in 'ABCD' and len(opt_str) > 1 and opt_str[1] in '.、 ':
                                opt_str = opt_str[2:].strip()
                            all_opts += '<div style="margin:1px 0;">' + f"<b>{letter}.</b> {opt_str}" + '</div>'
                        all_opts += '</div>'
                        render_latex_html(all_opts, font_size="16px", line_height="1.7")
                    
                    # 答案（与选项在同一行）
                    answer_text = q.get('correct_answer', '')
                    render_latex_html(f"<b>答案：</b>{answer_text}", font_size="16px")
                    
                    # 解析单独一行，完整显示（支持LaTeX）
                    explanation_text = q.get('explanation', '')
                    if explanation_text:
                        st.markdown("**解析：**")
                        # 处理解析文本，让每个选项（A选项、B选项、C选项、D选项）单独一行
                        import re
                        formatted_exp = explanation_text
                        formatted_exp = re.sub(r'(A选项)', r'<br>\1', formatted_exp)
                        formatted_exp = re.sub(r'(B选项)', r'<br>\1', formatted_exp)
                        formatted_exp = re.sub(r'(C选项)', r'<br>\1', formatted_exp)
                        formatted_exp = re.sub(r'(D选项)', r'<br>\1', formatted_exp)
                        formatted_exp = formatted_exp.replace('<br><br>', '<br>')
                        render_latex_html(formatted_exp, font_size="16px")
                    
                    st.markdown("---")
                    col_meta1, col_meta2, col_meta3 = st.columns(3)
                    with col_meta1:
                        st.caption(f"难度：{diff_stars}")
                    with col_meta2:
                        st.caption(f"练习次数：{q.get('times_used', 0)}")
                    with col_meta3:
                        st.caption(f"生成时间：{q.get('created_at', '')[:10]}")
        else:
            st.info("暂无题目，请先在「AI生成题目」中生成题目")
    
    # ---- 标签2：AI生成题目 ----
    with tab2:
        st.markdown("### 📝 AI生成新题目")
        st.caption("生成新题目自动存入题库")
        
        ai = init_ai_service()
        
        col1, col2 = st.columns(2)
        
        with col1:
            gen_knowledge = st.selectbox(
                "目标知识点",
                list(get_kp().keys()),
                key="gen_knowledge"
            )
        
        with col2:
            gen_difficulty = st.slider("题目难度", 1, 5, 2, key="gen_difficulty")
        
        gen_error_type = st.selectbox(
            "针对错误类型",
            ["概念混淆", "计算失误", "审题不清", "知识缺失", "逻辑推理错误"],
            key="gen_error_type"
        )
        
        gen_count = st.selectbox("生成题数", [3, 5, 8, 10, 15], key="gen_count")
        
        if st.button("🤖 AI批量生成题目", type="primary"):
            with st.spinner("AI正在生成题目，请稍候..."):
                try:
                    generated_questions = ai.generate_practice_questions(
                        target_knowledge=gen_knowledge,
                        error_type=gen_error_type,
                        difficulty=gen_difficulty,
                        count=gen_count
                    )
                    
                    if generated_questions:
                        saved_count = 0
                        for q in generated_questions:
                            q['knowledge_point'] = gen_knowledge
                            q['difficulty'] = gen_difficulty
                            db.add_question_to_bank(q)
                            saved_count += 1
                        
                        st.success(f"✅ 成功生成并保存 {saved_count} 道题目到题库！")
                        st.info("可在「题库概览」中查看所有题目")
                    else:
                        st.warning("未能生成题目，请稍后重试")
                
                except Exception as e:
                    st.error(f"生成失败：{str(e)}")
        
        st.markdown("---")
        st.markdown("#### 📌 快速操作")
        
        # 快速为所有知识点生成题目
        st.info("💡 提示：建议为每个知识点生成5-10道题目，确保学生有足够的练习量")
        
        quick_gen_kp = st.selectbox(
            "快速生成（选择知识点）",
            list(get_kp().keys()),
            key="quick_gen_kp"
        )
        
        if st.button(f"🚀 为「{quick_gen_kp}」生成10道基础题"):
            with st.spinner("生成中..."):
                try:
                    questions = ai.generate_practice_questions(
                        target_knowledge=quick_gen_kp,
                        error_type="知识缺失",
                        difficulty=2,
                        count=10
                    )
                    
                    saved_count = 0
                    for q in questions:
                        q['knowledge_point'] = quick_gen_kp
                        q['difficulty'] = 2
                        db.add_question_to_bank(q)
                        saved_count += 1
                    
                    st.success(f"✅ 为「{quick_gen_kp}」生成了 {saved_count} 道基础题！")
                except Exception as e:
                    st.error(f"生成失败：{str(e)}")
    
    # ---- 标签3：练习记录 ----
    with tab3:
        st.markdown("### 📖 练习记录")
        st.caption("查看学生练习历史，了解练习情况")
        
        # 获取可访问的班级学生
        accessible_classes = get_accessible_classes()
        if is_admin():
            students = db.get_students()
        else:
            students = []
            for cls_name in accessible_classes:
                students.extend(db.get_students(class_name=cls_name))
        if students:
            student_options = {s['name']: s for s in students}
            selected_name = st.selectbox("选择学生", list(student_options.keys()))
            selected_student = student_options[selected_name]
            
            # 获取练习历史
            history = db.get_student_practice_history(selected_student['id'], limit=100)
            
            col_h1, col_h2, col_h3 = st.columns(3)
            with col_h1:
                st.metric("练习总次数", len(history))
            with col_h2:
                correct = sum(1 for h in history if h.get('is_correct'))
                st.metric("正确次数", correct)
            with col_h3:
                rate = correct / len(history) * 100 if history else 0
                st.metric("正确率", f"{rate:.0f}%")
            
            if history:
                # 按日期分组展示
                history_by_date = {}
                for h in history:
                    date = h.get('practice_date', '')[:10]
                    if date not in history_by_date:
                        history_by_date[date] = []
                    history_by_date[date].append(h)
                
                for date, records in sorted(history_by_date.items(), reverse=True):
                    with st.expander(f"📅 {date} - {len(records)}题"):
                        for rec in records:
                            is_correct = rec.get('is_correct', 0)
                            status = "✅" if is_correct else "❌"
                            st.markdown(f"{status} **{rec.get('question_text', '')[:50]}...**")
                            if not is_correct:
                                st.write(f"   你的答案：{rec.get('student_answer', '')}")
                                st.write(f"   正确答案：{rec.get('correct_answer', '')}")
            else:
                st.info("暂无练习记录")
        else:
            st.warning("请先添加学生")
    
    # ---- 标签4：掌握统计 ----
    with tab4:
        st.markdown("### 📊 知识点掌握统计")
        st.caption("查看班级和个人的知识点掌握情况")
        
        # 选择班级（根据权限过滤）
        accessible_classes = get_accessible_classes()
        all_classes = db.get_classes()
        classes = [c for c in all_classes if c['class_name'] in accessible_classes]
        if classes:
            class_options = [c['class_name'] for c in classes]
            selected_class = st.selectbox("选择班级", class_options)
            
            # 班级整体掌握情况
            st.markdown("#### 🏫 班级整体掌握情况")
            
            class_mastery = db.get_class_knowledge_mastery(selected_class)
            
            if class_mastery:
                # 掌握情况表格
                mastery_df = pd.DataFrame(class_mastery)
                display_df = mastery_df[['knowledge_point', 'student_count', 'total_attempts', 'accuracy_rate', 'mastery_level']]
                display_df.columns = ['知识点', '练习人数', '练习次数', '正确率(%)', '掌握等级']
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                # 可视化
                st.markdown("##### 正确率对比")
                chart_data = pd.DataFrame({
                    '知识点': [m['knowledge_point'] for m in class_mastery],
                    '正确率(%)': [m.get('accuracy_rate', 0) or 0 for m in class_mastery]
                })
                st.bar_chart(chart_data.set_index('知识点'))
                
                # 薄弱知识点
                weak_kp = [m for m in class_mastery if (m.get('accuracy_rate', 0) or 0) < 70]
                
                if weak_kp:
                    st.markdown("#### 🔴 需要加强的知识点")
                    for kp_data in weak_kp:
                        with st.expander(f"⚠️ {kp_data['knowledge_point']} - 正确率{kp_data.get('accuracy_rate', 0):.0f}%"):
                            st.write(f"- 练习次数：{kp_data.get('total_attempts', 0)}")
                            st.write(f"- 正确次数：{kp_data.get('correct_count', 0)}")
                            st.write(f"- 练习人数：{kp_data.get('student_count', 0)}")
                            
                            # 获取薄弱学生
                            weak_students = db.get_weak_students(kp_data['knowledge_point'], selected_class)
                            if weak_students:
                                st.markdown("**薄弱学生：**")
                                for ws in weak_students[:5]:
                                    st.write(f"  - {ws['name']}（正确率{ws.get('accuracy_rate', 0):.0f}%）")
                            
                            # 一键生成针对练习
                            if st.button(f"📝 为{kp_data['knowledge_point']}生成强化练习", key=f"class_practice_{kp_data['knowledge_point']}"):
                                st.info("请到「练习推送」页面，选择此知识点进行练习")
            else:
                st.info("暂无班级练习数据")
            
            # 班级学生掌握情况
            st.markdown("---")
            st.markdown("#### 👨‍🎓 学生个人掌握情况")
            
            class_students = [s for s in students if s['class_name'] == selected_class]
            student_options = {s['name']: s for s in class_students}
            
            if student_options:
                selected_name = st.selectbox("选择学生", list(student_options.keys()), key="mastery_student")
                selected_student = student_options[selected_name]
                
                student_mastery = db.get_student_knowledge_mastery(selected_student['id'])
                
                if student_mastery:
                    mastery_df = pd.DataFrame(student_mastery)
                    display_df = mastery_df[['knowledge_point', 'total_attempts', 'correct_count', 'accuracy_rate', 'mastery_level']]
                    display_df.columns = ['知识点', '练习次数', '正确次数', '正确率(%)', '掌握等级']
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    
                    # 雷达图风格的展示
                    st.markdown("##### 掌握情况")
                    for m in student_mastery:
                        level = m.get('mastery_level', '未练习')
                        progress = m.get('accuracy_rate', 0) or 0
                        
                        progress_bar = st.progress(progress / 100, text=f"{m['knowledge_point']} {level} ({progress:.0f}%)")
                else:
                    st.info("该学生暂无练习记录")
        else:
            st.warning("请先添加班级和学生")
    
    # ---- 标签5：手动上传 ----
    with tab5:
        st.markdown("### 📥 手动上传题目")
        st.caption("通过Excel模板或文本链接手动添加题目到题库")
        
        upload_mode = st.radio("上传方式", ["📄 Excel模板上传", "🔗 文本粘贴上传"], horizontal=True)
        
        if upload_mode == "📄 Excel模板上传":
            st.markdown("#### 📥 Excel模板上传")
            
            # 下载模板
            template_data = {
                '题目内容': ['下列反应中，氧化剂是什么？$\\ce{2Fe^{3+} + Cu -> 2Fe^{2+} + Cu^{2+}}$', '配平化学方程式：$\\ce{Al + O2 -> Al2O3}$'],
                '题目类型': ['选择题', '填空题'],
                '知识点': ['氧化还原反应', '氧化还原反应'],
                '难度': [2, 3],
                '选项A': ['$\\ce{Fe^{3+}}$', ''],
                '选项B': ['$\\ce{Cu}$', ''],
                '选项C': ['$\\ce{Fe^{2+}}$', ''],
                '选项D': ['$\\ce{Cu^{2+}}$', ''],
                '正确答案': ['A', '$4Al + 3O2 = 2Al2O3$'],
                '解析': ['$\\ce{Fe^{3+}}$化合价降低，得电子，作氧化剂', '铝与氧气反应生成氧化铝']
            }
            template_df = pd.DataFrame(template_data)
            
            template_buffer = io.BytesIO()
            with pd.ExcelWriter(template_buffer, engine='openpyxl') as writer:
                template_df.to_excel(writer, index=False, sheet_name='题目模板')
                instructions = pd.DataFrame({
                    '字段说明': [
                        '题目内容: 必填，支持LaTeX格式（如$\\ce{H2O}$）',
                        '题目类型: 选择题/填空题/计算题/简答题',
                        '知识点: 必填，对应知识点库中的知识点',
                        '难度: 1-5，1最简单5最难',
                        '选项A-D: 选择题必填，其他题型留空',
                        '正确答案: 必填',
                        '解析: 可选，答案解析'
                    ]
                })
                instructions.to_excel(writer, index=False, sheet_name='填写说明')
            template_buffer.seek(0)
            
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                st.download_button(
                    label="📥 下载题目上传模板",
                    data=template_buffer,
                    file_name="题目上传模板.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
            with col_t2:
                st.info("""
                **模板格式说明：**
                - 题目内容支持LaTeX化学式格式
                - 选择题需填写选项A-D
                - 填空题/计算题选项留空即可
                """)
            
            st.markdown("---")
            
            uploaded_questions = st.file_uploader("选择Excel文件", type=["xlsx", "xls"], key="question_upload")
            
            if uploaded_questions is not None:
                try:
                    q_df = pd.read_excel(uploaded_questions, engine='openpyxl')
                    q_df.columns = q_df.columns.str.strip()
                    
                    required_cols = ['题目内容', '知识点', '正确答案']
                    missing = [c for c in required_cols if c not in q_df.columns]
                    if missing:
                        st.error(f"缺少必要列: {', '.join(missing)}")
                    else:
                        # 预览
                        st.markdown("##### 📋 题目预览")
                        preview_count = min(len(q_df), 10)
                        for i in range(preview_count):
                            row = q_df.iloc[i]
                            with st.expander(f"题目 {i+1}: {str(row.get('题目内容', ''))[:60]}..."):
                                st.write(f"**类型**: {row.get('题目类型', '未分类')}")
                                st.write(f"**知识点**: {row.get('知识点', '')}")
                                st.write(f"**难度**: {'⭐' * int(row.get('难度', 1))}")
                                opts = []
                                for opt_letter in ['A', 'B', 'C', 'D']:
                                    opt_val = row.get(f'选项{opt_letter}', '')
                                    if pd.notna(opt_val) and str(opt_val).strip():
                                        opts.append(f"{opt_letter}. {opt_val}")
                                if opts:
                                    st.write("**选项**:")
                                    for o in opts:
                                        st.write(f"　　{o}")
                                st.write(f"**答案**: {row.get('正确答案', '')}")
                                if pd.notna(row.get('解析', '')):
                                    st.write(f"**解析**: {row['解析']}")
                        
                        if len(q_df) > preview_count:
                            st.caption(f"... 还有 {len(q_df) - preview_count} 道题目")
                        
                        st.markdown(f"共 **{len(q_df)}** 道题目待导入")
                        
                        if st.button("✅ 确认导入到题库", type="primary", key="confirm_question_import"):
                            success_count = 0
                            error_count = 0
                            for idx, row in q_df.iterrows():
                                try:
                                    q_text = str(row.get('题目内容', '')).strip()
                                    kp = str(row.get('知识点', '')).strip()
                                    answer = str(row.get('正确答案', '')).strip()
                                    
                                    if not q_text or not kp or not answer:
                                        error_count += 1
                                        continue
                                    
                                    opts = []
                                    for opt_letter in ['A', 'B', 'C', 'D']:
                                        opt_val = row.get(f'选项{opt_letter}', '')
                                        if pd.notna(opt_val) and str(opt_val).strip():
                                            opts.append(str(opt_val).strip())
                                    
                                    db.add_question_to_bank({
                                        'question_text': q_text,
                                        'question_type': str(row.get('题目类型', '选择题')),
                                        'knowledge_point': kp,
                                        'difficulty': int(row.get('难度', 2)) if pd.notna(row.get('难度')) else 2,
                                        'answer': answer,
                                        'options': opts,
                                        'explanation': str(row.get('解析', '')) if pd.notna(row.get('解析')) else ''
                                    }, created_by='手动上传')
                                    success_count += 1
                                except Exception as e:
                                    error_count += 1
                            
                            st.success(f"✅ 导入完成：成功 {success_count} 道，失败 {error_count} 道")
                            st.rerun()
                
                except Exception as e:
                    st.error(f"文件读取失败: {str(e)}")
        
        else:
            st.markdown("#### 🔗 文本粘贴上传")
            st.caption("直接粘贴题目文本，每题之间用空行分隔")
            
            st.info("""
            **粘贴格式示例：**
            ```
            题目：下列反应中，氧化剂是什么？$\\ce{2Fe^{3+} + Cu -> 2Fe^{2+} + Cu^{2+}}$
            类型：选择题
            知识点：氧化还原反应
            难度：2
            A. $\\ce{Fe^{3+}}$
            B. $\\ce{Cu}$
            C. $\\ce{Fe^{2+}}$
            D. $\\ce{Cu^{2+}}$
            答案：A
            解析：$\\ce{Fe^{3+}}$化合价降低，得电子，作氧化剂
            ```
            """)
            
            paste_text = st.text_area("粘贴题目内容", height=300, placeholder="在此粘贴题目...")
            
            if paste_text and st.button("✅ 解析并导入", type="primary", key="parse_paste"):
                # 按空行分割题目
                blocks = [b.strip() for b in paste_text.split('\n\n') if b.strip()]
                
                parsed_questions = []
                parse_errors = 0
                
                for block in blocks:
                    lines = block.split('\n')
                    q_data = {
                        'question_text': '',
                        'question_type': '选择题',
                        'knowledge_point': '',
                        'difficulty': 2,
                        'options': [],
                        'answer': '',
                        'explanation': ''
                    }
                    
                    opts = []
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith('题目：') or line.startswith('题目:'):
                            q_data['question_text'] = line.split('：', 1)[-1].split(':', 1)[-1].strip()
                        elif line.startswith('类型：') or line.startswith('类型:'):
                            q_data['question_type'] = line.split('：', 1)[-1].split(':', 1)[-1].strip()
                        elif line.startswith('知识点：') or line.startswith('知识点:'):
                            q_data['knowledge_point'] = line.split('：', 1)[-1].split(':', 1)[-1].strip()
                        elif line.startswith('难度：') or line.startswith('难度:'):
                            try:
                                q_data['difficulty'] = int(line.split('：', 1)[-1].split(':', 1)[-1].strip())
                            except:
                                pass
                        elif line.startswith('答案：') or line.startswith('答案:'):
                            q_data['answer'] = line.split('：', 1)[-1].split(':', 1)[-1].strip()
                        elif line.startswith('解析：') or line.startswith('解析:'):
                            q_data['explanation'] = line.split('：', 1)[-1].split(':', 1)[-1].strip()
                        elif line and line[0] in 'ABCD' and (line[1] == '.' or line[1] == '、' or line[1] == ' '):
                            opts.append(line)
                    
                    q_data['options'] = opts
                    
                    if q_data['question_text'] and q_data['knowledge_point']:
                        parsed_questions.append(q_data)
                    else:
                        parse_errors += 1
                
                if parsed_questions:
                    st.success(f"解析成功：{len(parsed_questions)} 道题目" + (f"，{parse_errors} 道格式不正确已跳过" if parse_errors else ""))
                    
                    # 预览
                    for i, q in enumerate(parsed_questions[:5]):
                        with st.expander(f"题目 {i+1}: {q['question_text'][:50]}..."):
                            st.write(f"**类型**: {q['question_type']}")
                            st.write(f"**知识点**: {q['knowledge_point']}")
                            st.write(f"**难度**: {'⭐' * q['difficulty']}")
                            if q['options']:
                                for o in q['options']:
                                    st.write(f"　　{o}")
                            st.write(f"**答案**: {q['answer']}")
                            if q['explanation']:
                                st.write(f"**解析**: {q['explanation']}")
                    
                    if st.button("✅ 确认导入到题库", type="primary", key="confirm_paste_import"):
                        sc = 0
                        for q in parsed_questions:
                            try:
                                db.add_question_to_bank(q, created_by='手动上传')
                                sc += 1
                            except:
                                pass
                        st.success(f"✅ 成功导入 {sc} 道题目！")
                        st.rerun()
                else:
                    st.error("未能解析出有效题目，请检查格式")

# 系统设置
elif page == "⚙️ 系统设置":
    st.title("⚙️ 系统设置")
    
    # 导入配置管理模块
    from config_manager import save_config, load_config, get_api_key, get_provider, test_config
    
    st.markdown("---")

    # ========================================
    # 知识点库管理
    # ========================================
    st.markdown("#### 📚 知识点库管理")
    
    # 导入知识点管理模块
    from knowledge_manager import (
        load_knowledge_points, add_knowledge_point, update_knowledge_point,
        delete_knowledge_point, delete_all_knowledge_points,
        import_from_excel, import_from_json, confirm_import,
        get_excel_template, get_json_template, validate_knowledge_point,
        load_knowledge_structure, save_knowledge_structure,
        add_knowledge_chapter, add_core_content
    )
    
    # 初始化会话状态
    if 'import_preview_items' not in st.session_state:
        st.session_state.import_preview_items = []
    if 'editing_knowledge' not in st.session_state:
        st.session_state.editing_knowledge = None
    
    # 加载当前知识库
    knowledge_structure = load_knowledge_structure()
    
    # 子标签页
    sub_tab1, sub_tab2, sub_tab3 = st.tabs(["📖 知识库列表", "➕ 添加/编辑", "📥 批量导入"])
    
    # ========== 子标签1：知识库列表 ==========
    with sub_tab1:
        st.markdown("##### 当前知识库")
        
        # 统计三层结构
        total_chapters = len(knowledge_structure)
        total_points = sum(len(chapter.get('points', [])) for chapter in knowledge_structure.values())
        
        # 核心内容按顿号、逗号分隔符统计
        def count_core_items(core_name):
            """根据分隔符统计核心内容数量"""
            if not core_name:
                return 0
            # 支持顿号、逗号、分号、换行作为分隔符
            separators = ['、', '，', ',', '；', ';', '\n']
            count = 1
            for sep in separators:
                if sep in core_name:
                    count = len([x for x in core_name.split(sep) if x.strip()])
                    break
            return count
        
        total_cores = sum(
            sum(count_core_items(core.get('name', '')) for core in point.get('core_contents', []))
            for chapter in knowledge_structure.values()
            for point in chapter.get('points', [])
        )
        
        st.caption(f"共 {total_chapters} 个知识章节，{total_points} 个知识点，{total_cores} 个核心内容")
        
        # 统计信息 - 三层结构
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.metric("一级·知识章节", total_chapters)
        with col_stat2:
            st.metric("二级·知识点", total_points)
        with col_stat3:
            st.metric("三级·核心内容", total_cores)
        
        st.markdown("---")
        
        # 三层结构列表
        if knowledge_structure:
            for chapter_name, chapter_info in knowledge_structure.items():
                with st.expander(f"📁 **{chapter_name}** ({len(chapter_info.get('points', []))} 个知识点)"):
                    points = chapter_info.get('points', [])
                    for point in points:
                        point_name = point.get('name', '未命名')
                        core_contents = point.get('core_contents', [])
                        
                        st.markdown(f"  📄 **{point_name}** ({len(core_contents)} 个核心内容)")
                        
                        for core in core_contents:
                            core_name = core.get('name', '')
                            keywords = core.get('keywords', [])
                            common_errors = core.get('common_errors', [])
                            
                            st.markdown(f"    🔹 {core_name}")
                            if keywords:
                                st.caption(f"    关键词: {', '.join(keywords)}")
                            if common_errors:
                                st.caption(f"    常见错误: {', '.join(common_errors[:3])}")
                        
                        st.markdown("---")
                    
                    # 删除按钮
                    if st.button("🗑️ 删除章节", key=f"delete_chapter_{chapter_name}"):
                        if delete_knowledge_point(chapter_name):
                            st.success(f"已删除章节 '{chapter_name}'")
                            st.rerun()
                        else:
                            st.error("删除失败")
        else:
            st.info("暂无知识章节，请添加或导入")
        
        # 一键删除
        st.markdown("---")
        st.markdown("#### ⚠️ 危险操作")
        
        col_del1, col_del2 = st.columns(2)
        with col_del1:
            if st.button("🗑️ 一键删除所有知识点", type="secondary"):
                st.session_state.show_delete_confirm = True
        
        if st.session_state.get('show_delete_confirm'):
            st.warning("确定要删除所有自定义知识点吗？这将恢复到默认状态。")
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("确认删除", type="primary"):
                    if delete_all_knowledge_points():
                        st.success("✅ 已删除所有自定义知识点，恢复默认")
                        st.session_state.show_delete_confirm = False
                        st.rerun()
                    else:
                        st.error("删除失败")
            with col_no:
                if st.button("取消"):
                    st.session_state.show_delete_confirm = False
                    st.rerun()
    
    # ========== 子标签2：添加/编辑 ==========
    with sub_tab2:
        editing = st.session_state.get('editing_knowledge')
        
        # 选择已有章节进行编辑
        st.markdown("##### 📝 选择已有章节编辑")
        
        chapter_names = list(knowledge_structure.keys())
        selected_chapter = st.selectbox(
            "选择章节",
            ["-- 新建章节 --"] + chapter_names,
            key="select_chapter_edit"
        )
        
        if selected_chapter != "-- 新建章节 --" and selected_chapter in knowledge_structure:
            chapter_info = knowledge_structure[selected_chapter]
            
            # 显示章节信息
            col_info, col_del = st.columns([4, 1])
            with col_info:
                st.info(f"**章节编码**: {chapter_info.get('code', 'N/A')} | **知识点数**: {len(chapter_info.get('points', []))}")
            with col_del:
                if st.button("🗑️ 删除章节", key="del_selected_chapter"):
                    if delete_knowledge_point(selected_chapter):
                        st.success(f"已删除章节 '{selected_chapter}'")
                        st.rerun()
            
            # 编辑章节编码
            new_code = st.text_input("修改章节编码", value=chapter_info.get('code', ''), key="edit_chapter_code")
            if st.button("💾 保存章节编码", key="save_chapter_code"):
                knowledge_structure[selected_chapter]['code'] = new_code
                save_knowledge_structure(knowledge_structure)
                st.success("章节编码已更新")
                st.rerun()
            
            st.markdown("---")
            
            # 显示该章节下的知识点和核心内容
            st.markdown(f"**知识点列表**")
            for point in chapter_info.get('points', []):
                point_name = point.get('name', '')
                core_contents = point.get('core_contents', [])
                
                with st.expander(f"📄 {point_name} ({len(core_contents)} 个核心内容)"):
                    for i, core in enumerate(core_contents):
                        core_name = core.get('name', '')
                        keywords = core.get('keywords', [])
                        common_errors = core.get('common_errors', [])
                        
                        st.markdown(f"**核心内容 {i+1}**: {core_name}")
                        
                        # 编辑核心内容
                        col_edit1, col_edit2 = st.columns([3, 1])
                        with col_edit1:
                            new_core_name = st.text_input("核心内容名称", value=core_name, key=f"edit_core_name_{selected_chapter}_{point_name}_{i}")
                            new_keywords = st.text_input("关键词", value=', '.join(keywords), key=f"edit_keywords_{selected_chapter}_{point_name}_{i}")
                            new_errors = st.text_input("常见错误", value=', '.join(common_errors), key=f"edit_errors_{selected_chapter}_{point_name}_{i}")
                        with col_edit2:
                            if st.button("💾 保存", key=f"save_core_{selected_chapter}_{point_name}_{i}"):
                                core['name'] = new_core_name
                                core['keywords'] = [k.strip() for k in new_keywords.split(',') if k.strip()]
                                core['common_errors'] = [e.strip() for e in new_errors.split(',') if e.strip()]
                                save_knowledge_structure(knowledge_structure)
                                st.success("已保存")
                                st.rerun()
                            if st.button("🗑️ 删除", key=f"del_core_{selected_chapter}_{point_name}_{i}"):
                                core_contents.pop(i)
                                save_knowledge_structure(knowledge_structure)
                                st.success("已删除")
                                st.rerun()
                    
                    # 添加新核心内容
                    st.markdown("**➕ 添加新核心内容**")
                    new_core_name = st.text_input("核心内容名称", key=f"add_core_name_{selected_chapter}_{point_name}")
                    new_keywords = st.text_input("关键词", key=f"add_keywords_{selected_chapter}_{point_name}")
                    new_errors = st.text_input("常见错误", key=f"add_errors_{selected_chapter}_{point_name}")
                    if st.button("➕ 添加", key=f"add_core_{selected_chapter}_{point_name}"):
                        if new_core_name and new_keywords:
                            core_contents.append({
                                'name': new_core_name,
                                'keywords': [k.strip() for k in new_keywords.split(',') if k.strip()],
                                'common_errors': [e.strip() for e in new_errors.split(',') if e.strip()]
                            })
                            save_knowledge_structure(knowledge_structure)
                            st.success("已添加")
                            st.rerun()
            
            # 添加新知识点
            st.markdown("---")
            st.markdown("**➕ 添加新知识点**")
            new_point_name = st.text_input("知识点名称", key=f"add_point_name_{selected_chapter}")
            if st.button("➕ 添加知识点", key=f"add_point_{selected_chapter}"):
                if new_point_name:
                    chapter_info['points'].append({
                        'name': new_point_name,
                        'core_contents': []
                    })
                    save_knowledge_structure(knowledge_structure)
                    st.success(f"已添加知识点 '{new_point_name}'")
                    st.rerun()
        
        st.markdown("---")
        
        # 新建章节表单
        if selected_chapter == "-- 新建章节 --":
            st.markdown("##### ➕ 新建章节")
            
            with st.form("knowledge_form"):
                col_a, col_b = st.columns(2)
                
                with col_a:
                    chapter_name = st.text_input("一级·知识章节 *", help="如：氧化还原反应", key="form_chapter_name")
                    chapter_code = st.text_input("章节编码 *", max_chars=10, help="如：YHYY", key="form_chapter_code")
                
                with col_b:
                    point_name = st.text_input("二级·知识点 *", help="如：氧化还原反应基本概念", key="form_point_name")
                    core_name = st.text_input("三级·核心内容 *", help="如：氧化反应与还原反应", key="form_core_name")
                
                keywords_str = st.text_input("关键词 *", help="多个关键词用逗号分隔", key="form_keywords_str")
                common_errors_str = st.text_input("常见错误", help="多个错误用逗号分隔", key="form_errors_str")
                
                submitted = st.form_submit_button("💾 保存", type="primary")
                
                if submitted:
                    if not chapter_name or not chapter_code or not point_name or not core_name:
                        st.error("请填写所有必填项")
                    elif not keywords_str:
                        st.error("请填写关键词")
                    else:
                        keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
                        common_errors = [e.strip() for e in common_errors_str.split(',') if e.strip()]
                        
                        # 创建新章节
                        add_knowledge_chapter(chapter_name, chapter_code)
                        add_core_content(chapter_name, point_name, core_name, keywords, common_errors)
                        st.success(f"✅ 已添加 '{chapter_name} > {point_name} > {core_name}'")
                        st.rerun()
    
    # ========== 子标签3：批量导入 ==========
    with sub_tab3:
        st.markdown("##### 📥 批量导入知识库（三层结构）")
        
        # 下载模板
        st.markdown("**1. 下载导入模板**")
        
        col_temp1, col_temp2 = st.columns(2)
        
        with col_temp1:
            excel_template = get_excel_template()
            st.download_button(
                label="📄 下载Excel模板",
                data=excel_template,
                file_name="三层知识库导入模板.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        with col_temp2:
            json_template = get_json_template()
            st.download_button(
                label="📄 下载JSON模板",
                data=json_template,
                file_name="三层知识库导入模板.json",
                mime="application/json"
            )
        
        st.info("""
        **Excel模板格式说明（三层结构）：**
        - **一级·知识章节**：必填，如"氧化还原反应"
        - **章节编码**：必填，如"YHYY"
        - **二级·知识点**：必填，如"氧化还原反应基本概念"
        - **三级·核心内容**：必填，如"氧化反应与还原反应"
        - **关键词**：必填，多个用逗号分隔
        - **常见错误**：必填，多个用逗号分隔
        """)
        
        st.markdown("---")
        st.markdown("**2. 上传文件导入**")
        
        uploaded_file = st.file_uploader("选择文件", type=['xlsx', 'xls', 'json'], key="knowledge_import_uploader")
        
        if uploaded_file:
            file_content = uploaded_file.read()
            
            # 根据文件类型解析
            if uploaded_file.name.endswith('.json'):
                success, msg, items = import_from_json(file_content.decode('utf-8'))
            else:
                success, msg, items = import_from_excel(file_content)
            
            if items:
                st.session_state.import_preview_items = items
                
                if success:
                    st.success(msg)
                else:
                    st.warning(msg)
                
                # 预览导入内容
                st.markdown("**3. 预览导入内容**")
                
                # 按章节统计
                chapters = set(item['chapter_name'] for item in items)
                points = set((item['chapter_name'], item['point_name']) for item in items)
                st.caption(f"共 {len(chapters)} 个知识章节，{len(points)} 个知识点，{len(items)} 个核心内容待导入")
                
                for i, item in enumerate(items[:5]):  # 只显示前5个
                    with st.expander(f"{i+1}. {item['chapter_name']} > {item['point_name']} > {item['core_name']}"):
                        st.write(f"**章节编码**: {item['chapter_code']}")
                        st.write(f"**关键词**: {', '.join(item['keywords'])}")
                        if item['common_errors']:
                            st.write(f"**常见错误**: {', '.join(item['common_errors'])}")
                
                if len(items) > 5:
                    st.caption(f"... 还有 {len(items) - 5} 个核心内容")
                
                # 确认导入
                st.markdown("**4. 确认导入**")
                
                col_confirm, col_clear = st.columns(2)
                
                with col_confirm:
                    if st.button("✅ 确认导入到知识库", type="primary", key="confirm_knowledge_import"):
                        success_count, fail_count = confirm_import(items)
                        
                        if fail_count == 0:
                            st.success(f"✅ 成功导入 {success_count} 条核心内容！")
                        else:
                            st.warning(f"导入完成：成功 {success_count} 条，失败 {fail_count} 条")
                        
                        st.session_state.import_preview_items = []
                        st.rerun()
                
                with col_clear:
                    if st.button("❌ 清除预览", key="clear_knowledge_preview"):
                        st.session_state.import_preview_items = []
                        st.rerun()
            else:
                st.error(msg)


    st.markdown("---")

    # ========================================
    # 数据管理
    # ========================================
    st.markdown("#### 📊 数据管理")

    st.caption("导出系统数据或清空数据库（请谨慎操作）")
    
    # ---- 数据统计 ----
    st.markdown("#### 📊 当前数据统计")
    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
    
    with col_stat1:
        students_count = len(db.get_students())
        st.metric("学生总数", students_count)
    with col_stat2:
        classes_count = len(db.get_classes())
        st.metric("班级总数", classes_count)
    with col_stat3:
        diagnoses = db.get_all_diagnoses(limit=10000)
        diagnoses_count = len(diagnoses)
        st.metric("诊断记录", diagnoses_count)
    with col_stat4:
        questions = db.get_bank_questions(limit=10000)
        questions_count = len(questions)
        st.metric("题库题目", questions_count)
    
    st.markdown("---")
    
    # ---- 导出数据 ----
    st.markdown("#### 📥 导出数据")
    
    export_col1, export_col2 = st.columns([2, 1])
    
    with export_col1:
        st.info("""
        **导出内容：**
        - 学生信息（姓名、学号、班级、年级）
        - 诊断记录（学生、题目、错因、知识点、时间）
        - 题库题目（题目、答案、知识点、难度）
        - 练习记录（学生、题目、答案、结果）
        
        导出格式：Excel (.xlsx)，每个数据类型一个工作表
        """)
    
    with export_col2:
        if st.button("📥 导出全部数据", type="primary", key="export_all_data"):
            try:
                import io
                export_buffer = io.BytesIO()
                
                with pd.ExcelWriter(export_buffer, engine='openpyxl') as writer:
                    # 1. 学生信息
                    students_data = db.get_students()
                    if students_data:
                        students_df = pd.DataFrame(students_data)
                        students_df = students_df[['name', 'student_id', 'class_name', 'grade']]
                        students_df.columns = ['姓名', '学号', '班级', '年级']
                    else:
                        students_df = pd.DataFrame(columns=['姓名', '学号', '班级', '年级'])
                    students_df.to_excel(writer, index=False, sheet_name='学生信息')
                    
                    # 2. 诊断记录
                    diagnoses_data = db.get_all_diagnoses(limit=10000)
                    if diagnoses_data:
                        diag_df = pd.DataFrame(diagnoses_data)
                        diag_df = diag_df[['student_name', 'class_name', 'question_text', 'error_type_name', 
                                          'knowledge_point', 'diagnosis_detail', 'suggestion', 'diagnosed_at']]
                        diag_df.columns = ['学生姓名', '班级', '题目内容', '错误类型', '知识点', 
                                         '诊断详情', '改进建议', '诊断时间']
                    else:
                        diag_df = pd.DataFrame(columns=['学生姓名', '班级', '题目内容', '错误类型', 
                                                       '知识点', '诊断详情', '改进建议', '诊断时间'])
                    diag_df.to_excel(writer, index=False, sheet_name='诊断记录')
                    
                    # 3. 题库题目
                    questions_data = db.get_bank_questions(limit=10000)
                    if questions_data:
                        q_df = pd.DataFrame(questions_data)
                        q_df = q_df[['question_text', 'question_type', 'knowledge_point', 'difficulty',
                                    'correct_answer', 'explanation', 'times_used', 'times_correct']]
                        q_df.columns = ['题目内容', '题目类型', '知识点', '难度', '正确答案', 
                                      '解析', '使用次数', '正确次数']
                    else:
                        q_df = pd.DataFrame(columns=['题目内容', '题目类型', '知识点', '难度', 
                                                    '正确答案', '解析', '使用次数', '正确次数'])
                    q_df.to_excel(writer, index=False, sheet_name='题库题目')
                    
                    # 4. 练习记录
                    practice_records = db.get_all_practice_records(limit=10000)
                    if practice_records:
                        practice_df = pd.DataFrame(practice_records)
                        practice_df = practice_df[['student_name', 'question_text', 'student_answer',
                                                  'is_correct', 'practice_date', 'difficulty_level']]
                        practice_df.columns = ['学生姓名', '题目内容', '学生答案', '是否正确', 
                                             '练习时间', '难度等级']
                    else:
                        practice_df = pd.DataFrame(columns=['学生姓名', '题目内容', '学生答案', 
                                                          '是否正确', '练习时间', '难度等级'])
                    practice_df.to_excel(writer, index=False, sheet_name='练习记录')
                    
                    # 5. 班级信息
                    classes_data = db.get_classes()
                    if classes_data:
                        classes_df = pd.DataFrame(classes_data)
                    else:
                        classes_df = pd.DataFrame(columns=['class_name', 'grade'])
                    classes_df.to_excel(writer, index=False, sheet_name='班级信息')
                
                export_buffer.seek(0)
                st.session_state.export_data = export_buffer.getvalue()
                st.success("✅ 数据导出成功！")
                
            except Exception as e:
                st.error(f"导出失败：{str(e)}")
    
    # 下载按钮
    if 'export_data' in st.session_state:
        st.download_button(
            label="💾 下载导出文件",
            data=st.session_state.export_data,
            file_name=f"化学诊断系统数据导出_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
    
    st.markdown("---")
    
    # ---- 清空数据 ----
    st.markdown("#### 🗑️ 清空数据")
    st.warning("⚠️ 此操作不可恢复，请谨慎使用！建议先导出数据备份。")
    
    clear_options = st.multiselect(
        "选择要清空的数据",
        ["学生信息", "诊断记录", "题库题目", "练习记录", "全部数据"],
        help="选择要清空的数据类型"
    )
    
    if clear_options:
        st.markdown("**即将清空：**")
        for opt in clear_options:
            st.write(f"  - {opt}")
        
        # 二次确认
        confirm_text = st.text_input(
            '请输入"确认清空"以继续', 
            placeholder='输入：确认清空',
            key="clear_confirm_text"
        )
        
        if st.button("🗑️ 执行清空", type="secondary", key="do_clear_data"):
            if confirm_text == "确认清空":
                try:
                    cleared = []
                    
                    if "全部数据" in clear_options:
                        # 清空全部
                        db.clear_all_data()
                        cleared.append("全部数据")
                    else:
                        if "学生信息" in clear_options:
                            db.clear_students()
                            cleared.append("学生信息")
                        if "诊断记录" in clear_options:
                            db.clear_diagnoses()
                            cleared.append("诊断记录")
                        if "题库题目" in clear_options:
                            db.clear_questions()
                            cleared.append("题库题目")
                        if "练习记录" in clear_options:
                            db.clear_practice_records()
                            cleared.append("练习记录")
                    
                    cleared_text = '、'.join(cleared)
                    st.success(f"✅ {cleared_text} 已成功清空")
                    
                except Exception as e:
                    st.error(f"清空失败：{str(e)}")
            else:
                st.error("请输入正确的确认文字")
    
    st.markdown("---")
    
    # ---- 数据库信息 ----
    st.markdown("#### 📁 数据库信息")
    try:
        import os
        db_path = "data/chemistry_diagnosis.db"
        if os.path.exists(db_path):
            db_size = os.path.getsize(db_path)
            db_size_str = f"{db_size / 1024:.1f} KB" if db_size < 1024*1024 else f"{db_size / 1024 / 1024:.2f} MB"
            st.info(f"数据库文件：`{db_path}`，大小：**{db_size_str}**")
        else:
            st.info("数据库文件：内存模式")
    except:
        pass

# ========== 运行说明 ==========

    st.markdown("---")

    # ========================================
    # AI配置
    # ========================================
    st.markdown("#### 🔧 AI配置")

    st.markdown("##### AI服务配置")
    
    # 加载当前配置（使用 get_provider/get_api_key 确保 st.secrets 优先）
    current_provider = get_provider()
    current_api_key = get_api_key(current_provider)
    
    provider = st.selectbox(
        "选择AI服务商",
        ["qwen", "deepseek", "ollama"],
        index=["qwen", "deepseek", "ollama"].index(current_provider),
        format_func=lambda x: {
            "qwen": "通义千问（阿里云）",
            "deepseek": "DeepSeek（推荐）",
            "ollama": "Ollama（本地部署）"
        }[x]
    )
    
    if provider == "qwen":
        api_key = st.text_input("API Key", 
                               value=current_api_key if current_provider == "qwen" else "",
                               type="password", 
                               help="获取地址: https://dashscope.console.aliyun.com")
    elif provider == "deepseek":
        api_key = st.text_input("API Key", 
                               value=current_api_key if current_provider == "deepseek" else "",
                               type="password",
                               help="获取地址: https://platform.deepseek.com")
    else:
        api_key = st.text_input("Ollama服务地址", 
                               value=current_api_key if current_provider == "ollama" else "http://localhost:11434")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 保存配置", type="primary"):
            if api_key.strip():
                success = save_config(provider, api_key)
                if success:
                    st.success("✅ 配置已保存！")
                    st.info("配置已保存到本地文件，重启系统后仍然有效。")
                    # 重新初始化AI服务（同时重置全局缓存）
                    st.session_state.ai_service = None
                    _ai_module._ai_service = None
                else:
                    st.error("❌ 保存失败，请检查权限")
            else:
                st.warning("⚠️ 请输入API Key")
    
    with col2:
        if st.button("🗑️ 清除配置"):
            from config_manager import clear_config
            clear_config()
            st.success("配置已清除")
            st.session_state.ai_service = None
            _ai_module._ai_service = None
    
    st.markdown("---")
    st.markdown("### 连接测试")
    
    # 显示当前配置状态
    if current_api_key:
        st.info(f"当前配置: {current_provider} | API Key: {'已设置' if current_api_key else '未设置'}")
    else:
        st.warning("⚠️ 尚未配置API Key，请先保存配置")
    
    if st.button("🔌 测试连接"):
        with st.spinner("正在测试连接..."):
            result = test_config()
            if result["success"]:
                st.success(f"✅ {result['message']}")
            else:
                st.error(f"❌ {result['message']}")
                if "未配置" in result['message']:
                    st.info("💡 请先点击'保存配置'按钮保存API Key")


# ========== 教师管理页面（仅管理员可见）==========

if page == "👨‍🏫 教师管理":
    if not is_admin():
        st.error("您没有权限访问此页面")
        st.stop()
    
    st.title("👨‍🏫 教师管理")
    
    # 创建标签页
    tab_list, tab_add, tab_assign = st.tabs(["教师列表", "添加教师", "班级分配"])
    
    with tab_list:
        st.markdown("### 教师列表")
        
        teachers = db.get_all_teachers()
        if teachers:
            for teacher in teachers:
                with st.container():
                    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
                    with col1:
                        st.write(f"**{teacher['name']}**")
                    with col2:
                        st.write(f"账号：{teacher['username']}")
                    with col3:
                        role = "管理员" if teacher['role'] == 'admin' else "教师"
                        st.write(f"角色：{role}")
                    with col4:
                        if teacher['username'] != 'admin':  # 不能删除admin
                            if st.button("删除", key=f"del_teacher_{teacher['id']}"):
                                db.delete_teacher(teacher['id'])
                                st.success(f"已删除教师：{teacher['name']}")
                                st.rerun()
                    st.markdown("---")
        else:
            st.info("暂无教师账号")
    
    with tab_add:
        st.markdown("### 添加教师")
        
        with st.form("add_teacher_form"):
            name = st.text_input("姓名", placeholder="如：李老师")
            username = st.text_input("账号", placeholder="如：lilaoshi")
            password = st.text_input("密码", type="password", placeholder="初始密码")
            phone = st.text_input("联系电话", placeholder="可选")
            role = st.selectbox("角色", ["teacher", "admin"], format_func=lambda x: "教师" if x == "teacher" else "管理员")
            
            submitted = st.form_submit_button("添加教师", type="primary")
            
            if submitted:
                if name and username and password:
                    try:
                        teacher_id = db.add_teacher(name, username, password, role, phone)
                        st.success(f"✅ 教师 {name} 添加成功！")
                    except Exception as e:
                        st.error(f"添加失败：{str(e)}")
                else:
                    st.warning("请填写完整信息")
    
    with tab_assign:
        st.markdown("### 班级分配")
        
        # 选择教师
        teachers = db.get_all_teachers()
        teacher_options = {f"{t['name']} ({t['username']})": t['id'] for t in teachers if t['role'] == 'teacher'}
        
        if teacher_options:
            selected_teacher = st.selectbox("选择教师", list(teacher_options.keys()))
            teacher_id = teacher_options[selected_teacher]
            
            # 获取所有班级
            all_classes = db.get_classes()
            
            if all_classes:
                st.markdown("#### 分配班级")
                
                # 获取该教师已分配的班级
                assigned_classes = db.get_teacher_classes(teacher_id)
                assigned_class_ids = [c['id'] for c in assigned_classes]
                
                for cls in all_classes:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**{cls['class_name']}** ({cls.get('grade', '未设置')})")
                    with col2:
                        is_assigned = cls['id'] in assigned_class_ids
                        if is_assigned:
                            if st.button("取消分配", key=f"unassign_{teacher_id}_{cls['id']}"):
                                db.remove_class_from_teacher(teacher_id, cls['id'])
                                st.success(f"已取消分配 {cls['class_name']}")
                                st.rerun()
                        else:
                            if st.button("分配", key=f"assign_{teacher_id}_{cls['id']}"):
                                db.assign_class_to_teacher(teacher_id, cls['id'])
                                st.success(f"已分配 {cls['class_name']}")
                                st.rerun()
            else:
                st.info("暂无班级，请先在系统设置中添加班级")
        else:
            st.info("暂无普通教师账号，请先添加教师")

if __name__ == "__main__":
    pass
