# -*- coding: utf-8 -*-
"""
Steam游戏数据分析与可视化 - Streamlit网页应用

本应用使用Streamlit创建网页界面，展示Steam游戏数据的可视化分析结果，包括：
1. 上传CSV文件并显示数据预览
2. 筛选游戏（设置好评率区间和价格范围）
3. 显示各种图表：价格分布直方图、好评率与价格散点图、标签词云和柱状图
4. 显示"高好评+低价格"前10款游戏榜单
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import re
from collections import Counter
from datetime import datetime
import os
import io
import base64
from PIL import Image

# 检查必要的库是否已安装
try:
    import matplotlib.font_manager as fm
    from wordcloud import WordCloud
except ImportError as e:
    st.error(f"错误: 缺少必要的库 - {e}")
    st.info("请安装所需的库: pip install pandas matplotlib seaborn wordcloud streamlit pillow")
    st.stop()

# 设置页面配置
st.set_page_config(
    page_title="Steam游戏数据分析",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 添加CSS注入，使用Google Fonts的Noto Sans SC字体解决中文显示问题
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap');
    /* 全局字体设置 */
    html, body, [class*="css"], [class*="st-"], .stApp, .stApp * {
        font-family: 'Noto Sans SC', sans-serif !important;
    }
    /* 确保所有Streamlit元素使用Noto Sans SC字体 */
    .stPlotlyChart, .stChart, .matplotlib-figure, .stMarkdown, .stText, .stTitle, .stHeader, .stDataFrame,
    .stButton, .stSelectbox, .stMultiselect, .stSlider, .stRadio, .stCheckbox, .stNumberInput, .stTextInput,
    .stDateInput, .stTimeInput, .stFileUploader, .stTabs, .stExpander, .stSidebar, .stMetric, .stProgress,
    .stAlert, .stInfo, .stWarning, .stError, .stSuccess, .stTable, .stImage, .stAudio, .stVideo, .stDownloadButton {
        font-family: 'Noto Sans SC', sans-serif !important;
    }
    /* 确保图表中的文本也使用Noto Sans SC字体 */
    svg text, g text, .tick text, text.ytitle, text.xtitle, text.gtitle, .annotation-text, .legendtext {
        font-family: 'Noto Sans SC', sans-serif !important;
    }
    /* 强制应用于所有可能的文本元素 */
    * {
        font-family: 'Noto Sans SC', sans-serif !important;
    }
</style>
""", unsafe_allow_html=True)

# 设置中文显示
try:
    # 更可靠的中文字体设置方法
    import platform
    import matplotlib.font_manager as fm
    
    system = platform.system()
    
    if system == 'Windows':
        # Windows系统字体设置
        font_family = ['Microsoft YaHei', 'SimHei', 'SimSun', 'Arial Unicode MS', 'sans-serif']
        font_path = 'C:/Windows/Fonts/msyh.ttc'  # 微软雅黑字体路径
    elif system == 'Darwin':  # macOS
        # macOS系统字体设置
        font_family = ['Arial Unicode MS', 'PingFang SC', 'Heiti SC', 'sans-serif']
        font_path = '/System/Library/Fonts/PingFang.ttc'
    else:  # Linux等其他系统
        # Linux系统字体设置 - 不指定具体路径，使用字体名称
        font_family = ['Noto Sans SC', 'WenQuanYi Micro Hei', 'Droid Sans Fallback', 'sans-serif']
        font_path = None  # 不指定具体路径，让matplotlib自动查找
    
    # 创建通用字体属性对象，用于所有图表
    font_prop = fm.FontProperties(family=font_family)
    
    # 尝试注册字体，仅当字体路径存在时
    if font_path and os.path.exists(font_path):
        try:
            from matplotlib.font_manager import FontProperties, fontManager
            fontManager.addfont(font_path)
            st.sidebar.success(f"成功注册字体: {font_path}")
        except Exception as e:
            st.sidebar.warning(f"注册字体失败: {e}，将使用系统默认字体")
    
    # 设置字体
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = font_family
    plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号
    
    # 设置seaborn样式
    sns.set(style="whitegrid")
    
except Exception as e:
    st.warning(f"警告：设置中文字体时出错 - {e}")
    st.info("将尝试使用系统默认字体")
    # 创建一个默认字体属性对象
    font_prop = fm.FontProperties()

# 强制设置matplotlib使用中文字体
try:
    plt.rcParams['font.family'] = ['sans-serif']
    plt.rcParams['font.sans-serif'] = ['Noto Sans SC', 'Arial Unicode MS', 'SimHei', 'Microsoft YaHei']
    plt.rcParams['axes.unicode_minus'] = False
    
    # 打印当前字体设置，用于调试
    st.sidebar.markdown("### 调试信息")
    with st.sidebar.expander("字体设置", expanded=False):
        st.write(f"当前系统: {system}")
        st.write(f"字体家族: {plt.rcParams['font.family']}")
        st.write(f"无衬线字体: {plt.rcParams['font.sans-serif']}")
        if 'font_prop' in locals():
            st.write(f"字体属性: {font_prop.get_name()}")
        if 'current_font' in locals():
            st.write(f"当前字体路径: {current_font}")
except Exception as e:
    st.sidebar.warning(f"设置字体参数时出错: {e}")

# 数据处理函数
def clean_data(df):
    """
    清洗和预处理上传的Steam游戏数据
    """
    # 创建数据副本，避免修改原始数据
    df = df.copy()
    
    # 1. 处理价格数据
    def clean_price(price):
        if pd.isna(price) or price == "未知" or price == "免费":
            return 0.0
        # 提取数字部分
        price_match = re.search(r'\d+\.?\d*', str(price))
        if price_match:
            return float(price_match.group())
        return 0.0
    
    # 检查是否存在价格列
    if '原价' in df.columns:
        df['原价'] = df['原价'].apply(clean_price)
    if '折扣价' in df.columns:
        df['折扣价'] = df['折扣价'].apply(clean_price)
    
    # 创建价格列（优先使用折扣价，如果没有则使用原价）
    if '折扣价' in df.columns and '原价' in df.columns:
        df['价格'] = df['折扣价'].fillna(df['原价'])
    elif '折扣价' in df.columns:
        df['价格'] = df['折扣价']
    elif '原价' in df.columns:
        df['价格'] = df['原价']
    else:
        # 如果没有价格列，尝试查找其他可能的价格列
        price_columns = [col for col in df.columns if '价格' in col or 'price' in col.lower()]
        if price_columns:
            df['价格'] = df[price_columns[0]].apply(clean_price)
        else:
            # 如果找不到价格列，添加一个默认价格列
            df['价格'] = 0.0
            st.warning("警告：未找到价格列，将使用默认值0")
    
    # 2. 处理好评率数据
    def clean_rating(rating):
        if pd.isna(rating) or rating == "未知":
            return np.nan
        # 如果是百分比格式，提取数字部分
        if isinstance(rating, str) and '%' in rating:
            rating_match = re.search(r'(\d+)%', rating)
            if rating_match:
                return float(rating_match.group(1))
        # 如果已经是数字，直接返回
        if isinstance(rating, (int, float)):
            return float(rating)
        return np.nan
    
    # 检查是否存在好评率列
    if '详细好评率' in df.columns:
        df['好评率'] = df['详细好评率'].apply(clean_rating)
    if '基本好评率' in df.columns and '好评率' in df.columns:
        # 如果详细好评率为空，使用基本好评率
        df.loc[df['好评率'].isna(), '好评率'] = df.loc[df['好评率'].isna(), '基本好评率'].apply(clean_rating)
    elif '基本好评率' in df.columns:
        df['好评率'] = df['基本好评率'].apply(clean_rating)
    else:
        # 如果没有好评率列，尝试查找其他可能的好评率列
        rating_columns = [col for col in df.columns if '好评' in col or 'rating' in col.lower()]
        if rating_columns:
            df['好评率'] = df[rating_columns[0]].apply(clean_rating)
        else:
            # 如果找不到好评率列，添加一个默认好评率列
            df['好评率'] = np.nan
            st.warning("警告：未找到好评率列，将使用默认值NaN")
    
    # 3. 处理标签数据
    def clean_tags(tags):
        if pd.isna(tags) or tags == "未知" or tags == "[]":
            return []
        # 如果是字符串形式的列表，转换为实际列表
        if isinstance(tags, str):
            # 尝试解析字符串形式的列表
            try:
                # 移除字符串中的引号和方括号，然后分割
                tags = tags.replace("[", "").replace("]", "").replace("'", "").replace('"', "")
                if tags:
                    return [tag.strip() for tag in tags.split(',')]
                return []
            except:
                return []
        return []
    
    # 检查是否存在标签列
    if '详细标签' in df.columns:
        df['标签列表'] = df['详细标签'].apply(clean_tags)
    if '基本标签' in df.columns and '标签列表' in df.columns:
        # 如果详细标签为空，使用基本标签
        df.loc[df['标签列表'].apply(lambda x: len(x) == 0), '标签列表'] = \
            df.loc[df['标签列表'].apply(lambda x: len(x) == 0), '基本标签'].apply(clean_tags)
    elif '基本标签' in df.columns:
        df['标签列表'] = df['基本标签'].apply(clean_tags)
    else:
        # 如果没有标签列，尝试查找其他可能的标签列
        tag_columns = [col for col in df.columns if '标签' in col or 'tag' in col.lower()]
        if tag_columns:
            df['标签列表'] = df[tag_columns[0]].apply(clean_tags)
        else:
            # 如果找不到标签列，添加一个默认标签列
            df['标签列表'] = df.apply(lambda x: [], axis=1)
            st.warning("警告：未找到标签列，将使用默认值空列表")
    
    # 4. 处理发布时间数据
    def clean_date(date):
        if pd.isna(date) or date == "未知":
            return np.nan
        # 尝试解析日期
        try:
            # 如果是YYYY-MM-DD格式
            if re.match(r'\d{4}-\d{1,2}-\d{1,2}', str(date)):
                return pd.to_datetime(date)
            # 如果是其他格式，尝试提取年份
            year_match = re.search(r'(\d{4})', str(date))
            if year_match:
                return pd.to_datetime(year_match.group(1))
            return np.nan
        except:
            return np.nan
    
    # 检查是否存在发布时间列
    if '详细发布日期' in df.columns:
        df['发布时间'] = df['详细发布日期'].apply(clean_date)
    if '基本发布时间' in df.columns and '发布时间' in df.columns:
        # 如果详细发布日期为空，使用基本发布时间
        df.loc[df['发布时间'].isna(), '发布时间'] = df.loc[df['发布时间'].isna(), '基本发布时间'].apply(clean_date)
    elif '基本发布时间' in df.columns:
        df['发布时间'] = df['基本发布时间'].apply(clean_date)
    else:
        # 如果没有发布时间列，尝试查找其他可能的发布时间列
        date_columns = [col for col in df.columns if '发布' in col or '日期' in col or 'date' in col.lower() or 'release' in col.lower()]
        if date_columns:
            df['发布时间'] = df[date_columns[0]].apply(clean_date)
        else:
            # 如果找不到发布时间列，添加一个默认发布时间列
            df['发布时间'] = np.nan
            st.warning("警告：未找到发布时间列，将使用默认值NaN")
    
    # 添加年份列，用于时间趋势分析
    if '发布时间' in df.columns:
        df['发布年份'] = df['发布时间'].dt.year
    
    return df

# 图表生成函数
def plot_price_distribution(df):
    """
    绘制游戏价格分布直方图
    """
    # 过滤有效价格（非零且非空）
    valid_prices = df['价格'].dropna()
    valid_prices = valid_prices[valid_prices > 0]
    
    if valid_prices.empty:
        st.warning("没有有效的价格数据可供分析")
        return None
    
    # 计算价格统计信息
    price_stats = valid_prices.describe()
    
    # 绘制价格分布直方图
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # 获取字体路径
    try:
        font_path = fm.findfont(fm.FontProperties(family='Microsoft YaHei'))
    except:
        font_path = None
    
    sns.histplot(valid_prices, bins=30, kde=True, color='skyblue', ax=ax)
    
    # 添加标题和标签
    if font_path:
        ax.set_title('Steam游戏价格分布', fontsize=16, fontproperties=fm.FontProperties(fname=font_path))
        ax.set_xlabel('价格 (人民币)', fontsize=14, fontproperties=fm.FontProperties(fname=font_path))
        ax.set_ylabel('游戏数量', fontsize=14, fontproperties=fm.FontProperties(fname=font_path))
    else:
        ax.set_title('Steam游戏价格分布', fontsize=16)
        ax.set_xlabel('价格 (人民币)', fontsize=14)
        ax.set_ylabel('游戏数量', fontsize=14)
    
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # 添加均值线
    mean_price = price_stats['mean']
    ax.axvline(mean_price, color='red', linestyle='--', 
                label=f'平均价格: {mean_price:.2f}人民币')
    
    # 添加中位数线
    median_price = price_stats['50%']
    ax.axvline(median_price, color='green', linestyle='-.', 
                label=f'中位数价格: {median_price:.2f}人民币')
    
    if font_path:
        ax.legend(fontsize=12, prop=fm.FontProperties(fname=font_path))
    else:
        ax.legend(fontsize=12)
    
    plt.tight_layout()
    
    return fig, mean_price

def plot_rating_price_correlation(df):
    """
    绘制好评率与价格的散点图（带回归线）
    """
    # 过滤有效数据（价格和好评率都不为空）
    valid_data = df.dropna(subset=['价格', '好评率'])
    valid_data = valid_data[valid_data['价格'] > 0]
    
    if valid_data.empty:
        st.warning("没有同时包含价格和好评率的有效数据可供分析")
        return None, 0
    
    # 绘制散点图
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # 使用全局字体属性对象
    global font_prop
    
    # 使用seaborn的regplot绘制散点图和回归线
    sns.regplot(x='价格', y='好评率', data=valid_data, 
               scatter_kws={'alpha':0.5, 's':50, 'color':'blue'}, 
               line_kws={'color':'red', 'linewidth':2}, ax=ax)
    
    # 添加标题和标签，使用全局字体属性
    ax.set_title('Steam游戏价格与好评率关系', fontsize=16, fontproperties=font_prop)
    ax.set_xlabel('价格 (人民币)', fontsize=14, fontproperties=font_prop)
    ax.set_ylabel('好评率 (%)', fontsize=14, fontproperties=font_prop)
    
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # 计算相关系数
    corr = valid_data['价格'].corr(valid_data['好评率'])
    
    # 添加相关系数文本，使用全局字体属性
    ax.text(0.05, 0.95, f'相关系数: {corr:.2f}', 
            transform=ax.transAxes, fontsize=12,
            verticalalignment='top', fontproperties=font_prop)
    
    # 设置刻度标签字体
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontproperties(font_prop)
    
    plt.tight_layout()
    
    return fig, corr

def plot_tags_bar(df):
    """
    绘制热门标签柱状图
    """
    # 统计所有标签
    all_tags = [tag for tags in df['标签列表'] for tag in tags if tag]
    
    if not all_tags:
        st.warning("没有找到标签数据")
        return None
    
    # 统计标签频率
    tag_counter = Counter(all_tags)
    top_tags = tag_counter.most_common(20)
    
    # 创建DataFrame用于绘图
    tags_df = pd.DataFrame(top_tags, columns=['标签', '出现次数'])
    
    # 绘制柱状图
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # 使用全局字体属性对象
    global font_prop
    
    sns.barplot(x='出现次数', y='标签', data=tags_df, palette='viridis', ax=ax)
    
    # 添加标题和标签，使用全局字体属性
    ax.set_title('Steam游戏热门标签 Top 20', fontsize=16, fontproperties=font_prop)
    ax.set_xlabel('出现次数', fontsize=14, fontproperties=font_prop)
    ax.set_ylabel('标签', fontsize=14, fontproperties=font_prop)
    
    # 设置刻度标签字体
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontproperties(font_prop)
    
    # 添加数值标签
    for i, v in enumerate(tags_df['出现次数']):
        ax.text(v + 0.5, i, str(v), fontproperties=font_prop)
    
    plt.tight_layout()
    
    return fig

def plot_tags_wordcloud(df):
    """
    绘制标签词云
    """
    # 统计所有标签
    all_tags = [tag for tags in df['标签列表'] for tag in tags if tag]
    
    if not all_tags:
        st.warning("没有找到标签数据")
        return None
    
    # 统计标签频率
    tag_counter = Counter(all_tags)
    
    # 使用全局字体属性对象
    global font_prop
    
    # 创建词云对象 - 尝试多种方式设置字体
    try:
        # 尝试查找可用的中文字体
        font_path = None
        
        # 尝试使用matplotlib字体管理器查找字体
        import matplotlib.font_manager as fm
        font_files = fm.findSystemFonts()
        
        # 优先尝试找Noto Sans SC字体（Google字体，通过CSS已加载）
        noto_fonts = [f for f in font_files if 'noto' in f.lower() and ('sans' in f.lower() or 'sc' in f.lower())]
        if noto_fonts:
            font_path = noto_fonts[0]
            st.sidebar.success(f"找到Noto字体: {font_path}")
        
        # 其次尝试找其他常见中文字体
        if not font_path:
            chinese_fonts = [f for f in font_files if any(name in f.lower() for name in ['simhei', 'simsun', 'msyh', 'wqy', 'droid', 'noto'])]
            if chinese_fonts:
                font_path = chinese_fonts[0]
                st.sidebar.success(f"找到中文字体: {font_path}")
        
        # 创建词云对象
        wordcloud = WordCloud(
            width=800, 
            height=400, 
            background_color='white',
            max_words=100,
            max_font_size=150,
            random_state=42,
            font_path=font_path  # 使用找到的字体或None
        )
        
        # 生成词云
        wordcloud.generate_from_frequencies(tag_counter)
        
        # 绘制词云图
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.imshow(wordcloud, interpolation='bilinear')
        ax.axis('off')
        
        # 添加标题
        ax.set_title('Steam游戏标签词云', fontsize=16, fontproperties=font_prop)
        
        plt.tight_layout()
        
        return fig
    except Exception as e:
        st.error(f"生成词云时出错: {e}")
        st.info("由于字体问题，词云可能无法正确显示中文。正在尝试备用方案...")
        
        try:
            # 备用方案：使用PIL加载字体
            from PIL import ImageFont
            import tempfile
            import os
            
            # 尝试从网络下载Noto Sans SC字体并保存到临时文件
            st.warning("尝试使用备用方案生成词云...")
            
            # 使用不指定字体的方式创建词云
            wordcloud = WordCloud(
                width=800, 
                height=400, 
                background_color='white',
                max_words=100,
                max_font_size=150,
                random_state=42,
                # 完全不指定字体路径
                font_path=None
            )
            
            # 生成词云
            wordcloud.generate_from_frequencies(tag_counter)
            
            # 绘制词云图
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.imshow(wordcloud, interpolation='bilinear')
            ax.axis('off')
            
            # 添加标题
            ax.set_title('Steam游戏标签词云 (备用方案)', fontsize=16, fontproperties=font_prop)
            
            plt.tight_layout()
            
            st.success("成功使用备用方案生成词云！")
            return fig
            
        except Exception as backup_error:
            st.error(f"备用方案也失败了: {backup_error}")
            
            # 最后的备选方案：显示标签频率表格
            st.info("显示标签频率表格作为替代...")
            top_tags_df = pd.DataFrame(tag_counter.most_common(30), columns=['标签', '出现次数'])
            st.dataframe(top_tags_df)
            
            return None

def find_high_value_games(df, mean_price=None):
    """
    找出高性价比游戏（高好评率+低价格）
    """
    # 过滤有效数据（价格和好评率都不为空）
    valid_data = df.dropna(subset=['价格', '好评率'])
    valid_data = valid_data[valid_data['价格'] > 0]
    
    if valid_data.empty:
        st.warning("没有同时包含价格和好评率的有效数据可供分析")
        return None, None
    
    # 如果没有提供平均价格，计算平均价格
    if mean_price is None:
        mean_price = valid_data['价格'].mean()
    
    # 设置好评率和价格阈值
    rating_threshold = 85  # 85%好评率
    price_threshold = mean_price  # 低于平均价格
    
    # 筛选高性价比游戏
    high_value_games = valid_data[(valid_data['好评率'] >= rating_threshold) & 
                                 (valid_data['价格'] <= price_threshold)]
    
    # 按好评率降序排序
    high_value_games = high_value_games.sort_values(by='好评率', ascending=False)
    
    # 使用全局字体属性对象
    global font_prop
    
    # 绘制散点图，突出高性价比游戏
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # 绘制所有游戏的散点图（灰色）
    ax.scatter(valid_data['价格'], valid_data['好评率'], 
              alpha=0.5, s=50, color='gray', label='所有游戏')
    
    # 绘制高性价比游戏的散点图（红色）
    ax.scatter(high_value_games['价格'], high_value_games['好评率'], 
              alpha=0.8, s=50, color='red', label='高性价比游戏')
    
    # 添加阈值线
    ax.axhline(y=rating_threshold, color='r', linestyle='--', alpha=0.7, label=f'好评率 {rating_threshold}%')
    ax.axvline(x=price_threshold, color='b', linestyle='--', alpha=0.7, label=f'平均价格 {price_threshold:.2f} 元')
    
    # 添加标题和标签
    ax.set_title('高性价比游戏推荐', fontsize=16, fontproperties=font_prop)
    ax.set_xlabel('价格 (人民币)', fontsize=14, fontproperties=font_prop)
    ax.set_ylabel('好评率 (%)', fontsize=14, fontproperties=font_prop)
    
    # 设置刻度标签字体
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontproperties(font_prop)
    
    # 添加图例
    legend = ax.legend(loc='best', fontsize=12)
    # 设置图例中的字体
    for text in legend.get_texts():
        text.set_fontproperties(font_prop)
    
    ax.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    return fig, high_value_games

# 主函数
def main():
    # 设置标题
    st.title("🎮 Steam游戏数据分析与可视化")
    st.markdown("---")
    
    # 侧边栏 - 上传数据
    st.sidebar.header("📊 数据上传与筛选")
    
    # 上传CSV文件
    uploaded_file = st.sidebar.file_uploader("上传Steam游戏数据CSV文件", type=["csv"])
    
    # 示例数据选项
    use_example_data = st.sidebar.checkbox("使用示例数据", value=not bool(uploaded_file))
    
    # 加载数据
    if uploaded_file is not None:
        try:
            # 尝试读取上传的CSV文件
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
            st.sidebar.success(f"成功加载数据，共 {len(df)} 条记录")
        except Exception as e:
            st.sidebar.error(f"读取CSV文件时出错: {e}")
            st.stop()
    elif use_example_data:
        # 尝试读取本地示例数据
        try:
            df = pd.read_csv("steam_games_cleaned.csv", encoding='utf-8-sig')
            st.sidebar.success(f"成功加载示例数据，共 {len(df)} 条记录")
        except FileNotFoundError:
            st.sidebar.warning("找不到示例数据文件，将创建模拟数据")
            # 创建模拟数据
            import numpy as np
            
            # 创建一些示例游戏名称
            game_names = [
                "示例游戏1: 冒险之旅", 
                "示例游戏2: 策略大师", 
                "示例游戏3: 动作格斗", 
                "示例游戏4: 角色扮演", 
                "示例游戏5: 模拟经营",
                "示例游戏6: 休闲益智", 
                "示例游戏7: 射击游戏", 
                "示例游戏8: 恐怖生存", 
                "示例游戏9: 赛车竞速", 
                "示例游戏10: 体育竞技",
                "示例游戏11: 开放世界", 
                "示例游戏12: 多人在线", 
                "示例游戏13: 沙盒建造", 
                "示例游戏14: 解谜冒险", 
                "示例游戏15: 卡牌游戏",
                "示例游戏16: 音乐节奏", 
                "示例游戏17: 视觉小说", 
                "示例游戏18: 回合策略", 
                "示例游戏19: 生存建造", 
                "示例游戏20: roguelike"
            ]
            
            # 创建一些示例标签
            all_tags = [
                "动作", "冒险", "策略", "角色扮演", "模拟", "休闲", "独立", "大型多人在线", 
                "体育", "竞速", "射击", "恐怖", "解谜", "开放世界", "沙盒", "建造", "生存", 
                "卡牌", "roguelike", "回合制", "音乐", "视觉小说", "像素", "2D", "3D", 
                "第一人称", "第三人称", "多人", "单人", "合作", "竞技", "科幻", "奇幻", 
                "历史", "未来", "现代", "战争", "僵尸", "太空", "海洋"
            ]
            
            # 生成随机数据
            n_samples = 100
            data = {
                "游戏名称": np.random.choice(game_names, n_samples, replace=True),
                "原价": np.random.uniform(0, 200, n_samples),
                "折扣价": np.random.uniform(0, 150, n_samples),
                "好评率": np.random.uniform(60, 100, n_samples),
                "发布时间": pd.date_range(start='2015-01-01', periods=n_samples, freq='D'),
                "标签列表": [np.random.choice(all_tags, np.random.randint(3, 8), replace=False).tolist() for _ in range(n_samples)]
            }
            
            # 创建DataFrame
            df = pd.DataFrame(data)
            
            # 添加发布年份列
            df['发布年份'] = df['发布时间'].dt.year
            
            st.sidebar.success(f"已创建模拟数据，共 {len(df)} 条记录")
        except Exception as e:
            st.sidebar.error(f"加载示例数据时出错: {e}")
            st.stop()
    else:
        st.info("请上传CSV文件或选择使用示例数据")
        st.stop()
    
    # 数据预处理
    df = clean_data(df)
    
    # 侧边栏 - 数据筛选
    st.sidebar.subheader("数据筛选")
    
    # 价格范围筛选
    price_min = float(df['价格'].min())
    price_max = float(df['价格'].max())
    price_range = st.sidebar.slider(
        "价格范围 (人民币)",
        min_value=price_min,
        max_value=price_max,
        value=(price_min, price_max),
        step=1.0
    )
    
    # 好评率范围筛选
    rating_min = float(df['好评率'].min()) if not pd.isna(df['好评率'].min()) else 0.0
    rating_max = float(df['好评率'].max()) if not pd.isna(df['好评率'].max()) else 100.0
    rating_range = st.sidebar.slider(
        "好评率范围 (%)",
        min_value=rating_min,
        max_value=rating_max,
        value=(rating_min, rating_max),
        step=1.0
    )
    
    # 应用筛选
    filtered_df = df[
        (df['价格'] >= price_range[0]) & 
        (df['价格'] <= price_range[1]) & 
        (df['好评率'] >= rating_range[0]) & 
        (df['好评率'] <= rating_range[1])
    ]
    
    st.sidebar.info(f"筛选后的数据: {len(filtered_df)} 条记录")
    
    # 主页面 - 数据预览
    st.header("📋 数据预览")
    st.dataframe(filtered_df.head(10))
    
    # 下载筛选后的数据
    def get_csv_download_link(df, filename="filtered_data.csv"):
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        b64 = base64.b64encode(csv.encode('utf-8-sig')).decode()
        href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">下载筛选后的数据</a>'
        return href
    
    st.markdown(get_csv_download_link(filtered_df), unsafe_allow_html=True)
    st.markdown("---")
    
    # 主页面 - 数据可视化
    st.header("📈 数据可视化")
    
    # 创建选项卡
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["价格分布", "价格与好评率", "热门标签柱状图", "标签词云", "高性价比游戏"])
    
    # 选项卡1: 价格分布直方图
    with tab1:
        st.subheader("Steam游戏价格分布")
        fig_price, mean_price = plot_price_distribution(filtered_df)
        if fig_price:
            st.pyplot(fig_price)
            st.markdown(f"**价格统计信息:**")
            price_stats = filtered_df['价格'].dropna()
            price_stats = price_stats[price_stats > 0].describe()
            st.write(f"- 平均价格: {price_stats['mean']:.2f} 人民币")
            st.write(f"- 中位数价格: {price_stats['50%']:.2f} 人民币")
            st.write(f"- 最高价格: {price_stats['max']:.2f} 人民币")
            st.write(f"- 最低价格: {price_stats['min']:.2f} 人民币")
            st.write(f"- 价格标准差: {price_stats['std']:.2f} 人民币")
    
    # 选项卡2: 好评率与价格散点图
    with tab2:
        st.subheader("Steam游戏价格与好评率关系")
        fig_corr, corr = plot_rating_price_correlation(filtered_df)
        if fig_corr:
            st.pyplot(fig_corr)
            st.markdown(f"**相关性分析:**")
            if corr > 0.5:
                st.write(f"- 相关系数: {corr:.2f} (强正相关)")
                st.write("- 结论: 好评率与价格之间存在较强正相关性")
                st.write("- 趋势: 价格越高，好评率越高")
            elif corr > 0.3:
                st.write(f"- 相关系数: {corr:.2f} (中等正相关)")
                st.write("- 结论: 好评率与价格之间存在中等正相关性")
                st.write("- 趋势: 价格越高，好评率略有提高")
            elif corr > 0:
                st.write(f"- 相关系数: {corr:.2f} (弱正相关)")
                st.write("- 结论: 好评率与价格之间存在弱正相关性")
                st.write("- 趋势: 价格与好评率关系不明显")
            elif corr > -0.3:
                st.write(f"- 相关系数: {corr:.2f} (弱负相关)")
                st.write("- 结论: 好评率与价格之间存在弱负相关性")
                st.write("- 趋势: 价格与好评率关系不明显")
            elif corr > -0.5:
                st.write(f"- 相关系数: {corr:.2f} (中等负相关)")
                st.write("- 结论: 好评率与价格之间存在中等负相关性")
                st.write("- 趋势: 价格越高，好评率略有下降")
            else:
                st.write(f"- 相关系数: {corr:.2f} (强负相关)")
                st.write("- 结论: 好评率与价格之间存在较强负相关性")
                st.write("- 趋势: 价格越高，好评率越低")
    
    # 选项卡3: 热门标签柱状图
    with tab3:
        st.subheader("Steam游戏热门标签 Top 20")
        fig_tags = plot_tags_bar(filtered_df)
        if fig_tags:
            st.pyplot(fig_tags)
            
            # 统计所有标签
            all_tags = [tag for tags in filtered_df['标签列表'] for tag in tags if tag]
            tag_counter = Counter(all_tags)
            top_tags = tag_counter.most_common(20)
            
            st.markdown(f"**热门标签统计:**")
            for tag, count in top_tags[:5]:
                st.write(f"- {tag}: {count} 款游戏")
            
            with st.expander("查看更多标签统计"):
                for tag, count in top_tags[5:]:
                    st.write(f"- {tag}: {count} 款游戏")
    
    # 选项卡4: 标签词云
    with tab4:
        st.subheader("Steam游戏标签词云")
        fig_wordcloud = plot_tags_wordcloud(filtered_df)
        if fig_wordcloud:
            st.pyplot(fig_wordcloud)
    
    # 选项卡5: 高性价比游戏
    with tab5:
        st.subheader("高性价比游戏推荐")
        fig_high_value, high_value_games = find_high_value_games(filtered_df, mean_price)
        if fig_high_value and high_value_games is not None:
            st.pyplot(fig_high_value)
            
            st.markdown(f"**高性价比游戏 Top 10:**")
            top_games = high_value_games.head(10)
            
            # 创建结果DataFrame
            result_df = top_games[['游戏名称', '价格', '好评率']].copy()
            if 'AppID' in top_games.columns:
                result_df['AppID'] = top_games['AppID']
            
            st.dataframe(result_df)
            
            # 下载高性价比游戏列表
            st.markdown(get_csv_download_link(high_value_games, "高性价比游戏推荐列表.csv"), unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center">
        <p>Steam游戏数据分析与可视化 - Streamlit网页应用</p>
    </div>
    """, unsafe_allow_html=True)

# 运行应用
if __name__ == "__main__":
    main()
    
# 设置全局字体属性对象
import platform

font_prop = None
try:
    # 尝试查找中文字体，优先级：Noto Sans SC > Microsoft YaHei > SimHei
    font_paths = []
    for font_name in ['Noto Sans SC', 'Microsoft YaHei', 'SimHei', 'SimSun', 'WenQuanYi Micro Hei', 'Droid Sans Fallback']:
        try:
            font_path = fm.findfont(fm.FontProperties(family=font_name))
            if font_path and os.path.exists(font_path):
                font_paths.append((font_name, font_path))
                st.sidebar.success(f"成功加载中文字体: {font_name}")
                break
        except Exception as e:
            st.sidebar.warning(f"尝试加载字体 {font_name} 失败: {str(e)}")
            continue
    
    if font_paths:
        font_name, font_path = font_paths[0]  # 使用找到的第一个字体
        font_prop = fm.FontProperties(fname=font_path)
    else:
        # 如果找不到中文字体，使用默认字体
        font_prop = fm.FontProperties()
        st.sidebar.warning("未找到中文字体，使用默认字体")
        
    # 添加调试信息
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st.sidebar.info(f"字体路径: {font_path}")
    else:
        st.sidebar.info("未找到中文字体路径")
    
except Exception as e:
    st.sidebar.error(f"设置字体时出错: {e}")
    font_prop = fm.FontProperties()
    
    st.sidebar.info(f"当前系统: {platform.system()}")
    if font_paths:
        st