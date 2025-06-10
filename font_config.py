# -*- coding: utf-8 -*-
"""
字体配置模块
用于解决Streamlit Cloud环境中的中文字体显示问题
"""

import base64
import os
import tempfile
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.font_manager import FontProperties
import streamlit as st

# 全局字体属性对象
font_prop = None
font_path = None

def setup_chinese_font():
    """
    设置中文字体，优先使用系统字体
    """
    global font_prop, font_path
    
    try:
        # 查找系统中的中文字体
        chinese_fonts = []
        for font in fm.fontManager.ttflist:
            font_name = font.name.lower()
            if any(name in font_name for name in [
                'microsoft yahei', 'simhei', 'simsun', 'noto sans sc', 
                'source han sans', 'pingfang', 'heiti', 'dengxian'
            ]):
                chinese_fonts.append((font.fname, font.name))
        
        if chinese_fonts:
            # 使用找到的第一个中文字体
            font_path, font_name = chinese_fonts[0]
            font_prop = FontProperties(fname=font_path)
            
            # 设置matplotlib的默认字体
            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['font.sans-serif'] = [font_name] + plt.rcParams['font.sans-serif']
            plt.rcParams['axes.unicode_minus'] = False
            
            # 清除字体缓存
            fm.fontManager.addfont(font_path)
            
            st.success(f"✅ 成功设置中文字体: {font_name}")
            return font_prop, font_path  # 修改这里
        else:
            st.warning("⚠️ 未找到系统中文字体，中文可能显示为方框")
            return None, None  # 修改这里
            
    except Exception as e:
        st.error(f"❌ 字体设置失败: {e}")
        return None, None  # 修改这里

def get_wordcloud_font():
    """
    获取词云专用的字体路径
    """
    global font_path
    
    if font_path and os.path.exists(font_path):
        return font_path
    
    # 如果全局字体路径不可用，尝试查找系统字体
    try:
        for font in fm.fontManager.ttflist:
            font_name = font.name.lower()
            if any(name in font_name for name in [
                'microsoft yahei', 'simhei', 'simsun', 'noto sans sc'
            ]):
                return font.fname
    except:
        pass
    
    return None

def apply_font_to_figure(fig):
    """
    将中文字体应用到matplotlib图形的所有文本元素
    """
    global font_prop
    
    if font_prop is None:
        return
    
    try:
        # 应用字体到图形中的所有文本元素
        for ax in fig.get_axes():
            # 设置标题字体
            if ax.get_title():
                ax.set_title(ax.get_title(), fontproperties=font_prop)
            
            # 设置轴标签字体
            if ax.get_xlabel():
                ax.set_xlabel(ax.get_xlabel(), fontproperties=font_prop)
            if ax.get_ylabel():
                ax.set_ylabel(ax.get_ylabel(), fontproperties=font_prop)
            
            # 设置刻度标签字体
            for label in ax.get_xticklabels():
                label.set_fontproperties(font_prop)
            for label in ax.get_yticklabels():
                label.set_fontproperties(font_prop)
            
            # 设置图例字体
            legend = ax.get_legend()
            if legend:
                for text in legend.get_texts():
                    text.set_fontproperties(font_prop)
            
            # 设置文本注释字体
            for text in ax.texts:
                text.set_fontproperties(font_prop)
                
    except Exception as e:
         st.warning(f"应用字体时出现问题: {e}")