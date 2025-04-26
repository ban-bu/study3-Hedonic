# 导入所有必要的基础依赖
import streamlit as st
import warnings
warnings.filterwarnings('ignore')

from PIL import Image, ImageDraw
import requests
from io import BytesIO
# 重新组织cairosvg导入逻辑，避免错误
# 完全移除cairosvg依赖，只使用svglib或其他备选方案
import base64
import numpy as np
import os
import pandas as pd
import uuid
import datetime
import json
import random
import time

# Requires installation: pip install streamlit-image-coordinates
from streamlit_image_coordinates import streamlit_image_coordinates
from streamlit.components.v1 import html
from streamlit_drawable_canvas import st_canvas

# 导入OpenAI配置
from openai import OpenAI
API_KEY = "sk-lNVAREVHjj386FDCd9McOL7k66DZCUkTp6IbV0u9970qqdlg"
BASE_URL = "https://api.deepbricks.ai/v1/"
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# 导入面料纹理模块
from fabric_texture import apply_fabric_texture

# 导入SVG处理功能
from svg_utils import convert_svg_to_png

# 导入分拆出去的各页面模块
from welcome_page import show_welcome_page
from survey_page import show_survey_page, initialize_experiment_data, save_experiment_data
from low_no_explanation import show_low_recommendation_without_explanation
from low_with_explanation import show_low_recommendation_with_explanation
from high_no_explanation import show_high_recommendation_without_explanation
from high_with_explanation import show_high_recommendation_with_explanation


# Page configuration
st.set_page_config(
    page_title="T-shirt Design Platform",
    page_icon="👕",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS styles
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
        border-radius: 12px;
        height: 3em;
    }
    .stButton>button:hover {
        background-color: #45a049;
    }
    div[data-testid="stHeader"] {
        background-color: rgba(0,0,0,0);
    }
    div[data-testid="stToolbar"] {
        background-color: rgba(0,0,0,0);
        right: 2rem;
    }
    div.stTabs button {
        background-color: #f0f2f6;
        border-radius: 4px 4px 0 0;
        padding: 10px 20px;
        margin-right: 5px;
    }
    div.stTabs button[aria-selected="true"] {
        background-color: #e6e9ef;
        font-weight: bold;
    }
    .design-area {
        border: 2px dashed #f63366;
        border-radius: 5px;
        padding: 10px;
        margin-bottom: 20px;
    }
    .highlight-text {
        color: #f63366;
        font-weight: bold;
    }
    .purchase-intent {
        background-color: #f9f9f9;
        padding: 20px;
        border-radius: 10px;
        margin: 20px 0;
    }
    .rating-container {
        display: flex;
        justify-content: space-between;
        margin: 20px 0;
    }
    .welcome-card {
        background-color: #f8f9fa;
        padding: 30px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 30px;
    }
    .group-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 10px 0;
        border: 1px solid #e0e0e0;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .group-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
    }
    .design-gallery {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
        gap: 10px;
        margin: 20px 0;
    }
    .design-item {
        border: 2px solid transparent;
        border-radius: 5px;
        transition: border-color 0.2s;
        cursor: pointer;
    }
    .design-item.selected {
        border-color: #f63366;
    }
    .movable-box {
        cursor: move;
    }
</style>
""", unsafe_allow_html=True)

# 数据文件路径 - 共享常量
DATA_FILE = "experiment_data.csv"

# Preset design options (using local images)
PRESET_DESIGNS = {
    "Floral Pattern": "preset_designs/floral.png",
    "Geometric Pattern": "preset_designs/geometric.png",
    "Abstract Art": "preset_designs/abstract.png",
    "Minimalist Lines": "preset_designs/minimalist.png",
    "Animal Pattern": "preset_designs/animal.png"
}

# Initialize session state
if 'openai_api_key' not in st.session_state:
    st.session_state.openai_api_key = os.getenv("OPENAI_API_KEY", "")
if 'first_time' not in st.session_state:
    st.session_state.first_time = True
if 'experiment_group' not in st.session_state:
    # 直接设置实验组为study3
    st.session_state.experiment_group = "AI Customization Group"
if 'page' not in st.session_state:
    # 直接设置页面为design，跳过welcome页面
    st.session_state.page = "design"
if 'user_id' not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())
if 'start_time' not in st.session_state:
    st.session_state.start_time = datetime.datetime.now()
if 'user_info' not in st.session_state:
    # 设置默认用户信息
    st.session_state.user_info = {
        'age': '25-34',
        'gender': 'Female',
        'shopping_frequency': 'Several times a month',
        'customization_experience': 'Sometimes',
        'ai_attitude': 'Positive',
        'uniqueness_importance': 'Very important'
    }
if 'base_image' not in st.session_state:
    st.session_state.base_image = None
if 'current_image' not in st.session_state:
    st.session_state.current_image = None
if 'current_box_position' not in st.session_state:
    st.session_state.current_box_position = None
if 'generated_design' not in st.session_state:
    st.session_state.generated_design = None
if 'final_design' not in st.session_state:
    st.session_state.final_design = None
if 'submitted' not in st.session_state:
    st.session_state.submitted = False
if 'selected_preset' not in st.session_state:
    st.session_state.selected_preset = None
if 'preset_design' not in st.session_state:
    st.session_state.preset_design = None
if 'drawn_design' not in st.session_state:
    st.session_state.drawn_design = None
if 'preset_position' not in st.session_state:
    st.session_state.preset_position = (0, 0)  # 默认居中，表示相对红框左上角的偏移
if 'preset_scale' not in st.session_state:
    st.session_state.preset_scale = 40  # 默认为40%
if 'design_mode' not in st.session_state:
    st.session_state.design_mode = "preset"  # 默认使用预设设计模式
if 'fabric_type' not in st.session_state:
    st.session_state.fabric_type = None  # 初始状态下没有特定面料类型
if 'apply_texture' not in st.session_state:
    st.session_state.apply_texture = False  # 初始状态下不应用纹理

# Ensure data file exists
initialize_experiment_data()

# Main program control logic
def main():
    # Initialize data file
    initialize_experiment_data()
    
    # Display different content based on current page
    if st.session_state.page == "welcome":
        # 直接跳转到design页面，不显示welcome页面
        st.session_state.page = "design"
        st.rerun()
    elif st.session_state.page == "design":
        # 直接调用study3的页面函数
        show_low_recommendation_without_explanation()
    elif st.session_state.page == "survey":
        # 将问卷页面也重定向到设计页面，不再显示问卷
        st.session_state.page = "design"
        st.rerun()
    elif st.session_state.page == "thank_you":
        # 感谢页面也重定向到设计页面
        st.session_state.page = "design"
        st.rerun()

# Run application
if __name__ == "__main__":
    main()

# 欢迎页面
def show_welcome_page():
    st.title("👕 T-shirt Design Experiment")
    st.markdown("### Welcome to our T-shirt design study!")
    st.write("In this experiment, you will design a custom t-shirt with different levels of AI assistance.")
    
    # 创建两列布局
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Demographic Information")
        
        # 收集用户人口统计信息
        age = st.selectbox("Age Group:", [
            "18-24", "25-34", "35-44", "45-54", "55-64", "65+"
        ])
        
        gender = st.selectbox("Gender:", [
            "Male", "Female", "Non-binary", "Prefer not to say"
        ])
        
        shopping = st.selectbox("How often do you shop for clothes?", [
            "Several times a week", 
            "Several times a month", 
            "Once a month", 
            "Once every few months", 
            "Once or twice a year", 
            "Rarely"
        ])
        
        customization = st.selectbox("How often do you customize your products?", [
            "Very often", "Often", "Sometimes", "Rarely", "Never"
        ])
        
        ai_attitude = st.selectbox("What is your general attitude towards AI?", [
            "Very positive", "Positive", "Neutral", "Negative", "Very negative"
        ])
        
        uniqueness = st.selectbox("How important is it for you to have unique products?", [
            "Extremely important", "Very important", "Moderately important", 
            "Slightly important", "Not important at all"
        ])
    
    with col2:
        st.markdown("### Study Information")
        st.write("""
        This study aims to understand how different levels of AI recommendation 
        affect the user experience in a t-shirt design task.
        
        You will be assigned to one of the following groups:
        
        - **Control Group**: Design t-shirts without AI help
        - **Low Recommendation**: AI provides minimal recommendations
        - **Medium Recommendation**: AI provides moderate recommendations
        - **High Recommendation**: AI provides substantial recommendations
        - **AI Creation Group**: AI creates based on your input
        - **AI Customization Group**: You customize AI-generated templates
        
        Please complete the entire experiment, which will take approximately 
        10-15 minutes of your time.
        """)
        
        # 收集API密钥
        api_key = st.text_input("Enter your OpenAI API Key:", type="password")
        if api_key:
            st.session_state.openai_api_key = api_key
        
        # 提交按钮
        if st.button("Start Experiment", use_container_width=True):
            # 保存用户信息
            st.session_state.user_info = {
                'age': age,
                'gender': gender,
                'shopping_frequency': shopping,
                'customization_experience': customization,
                'ai_attitude': ai_attitude,
                'uniqueness_importance': uniqueness
            }
            
            # 随机分配实验组，如果没有特别指定的话
            if not st.session_state.get("experiment_group"):
                groups = [
                    "Control Group",
                    "Low Recommendation Group",
                    "Medium Recommendation Group",
                    "High Recommendation Group",
                    "AI Creation Group",
                    "AI Customization Group"
                ]
                st.session_state.experiment_group = random.choice(groups)
            
            # 设置页面为设计页面
            st.session_state.page = "design"
            st.rerun()

# 问卷调查页面
def show_survey_page():
    st.title("👕 T-shirt Design Experience Survey")
    st.markdown("### Thank you for completing the design task!")
    st.write("Please take a moment to share your experience with us:")
    
    q1 = st.selectbox(
        "1. How satisfied are you with your final t-shirt design?",
        ["Extremely satisfied", "Very satisfied", "Moderately satisfied", 
         "Slightly satisfied", "Not satisfied at all"]
    )
    
    q2 = st.selectbox(
        "2. How helpful was the AI in your design process?",
        ["Extremely helpful", "Very helpful", "Moderately helpful", 
         "Slightly helpful", "Not helpful at all"]
    )
    
    q3 = st.selectbox(
        "3. How easy was it to use the design interface?",
        ["Extremely easy", "Very easy", "Moderately easy", 
         "Slightly difficult", "Very difficult"]
    )
    
    q4 = st.selectbox(
        "4. How much creative control did you feel you had?",
        ["Complete control", "Substantial control", "Moderate control", 
         "Little control", "No control at all"]
    )
    
    q5 = st.selectbox(
        "5. How likely are you to use an AI-assisted design tool in the future?",
        ["Extremely likely", "Very likely", "Moderately likely", 
         "Slightly likely", "Not likely at all"]
    )
    
    q6 = st.selectbox(
        "6. The AI recommendations matched my preferences.",
        ["Strongly agree", "Agree", "Neither agree nor disagree", 
         "Disagree", "Strongly disagree"]
    )
    
    q7 = st.selectbox(
        "7. I felt the AI understood what I wanted.",
        ["Strongly agree", "Agree", "Neither agree nor disagree", 
         "Disagree", "Strongly disagree"]
    )
    
    q8 = st.text_area(
        "8. What improvements would you suggest for the AI design assistant?",
        ""
    )
    
    # 提交按钮
    if st.button("Submit Survey", use_container_width=True):
        # 保存问卷回答
        st.session_state.survey_responses = {
            'satisfaction': q1,
            'ai_helpfulness': q2,
            'interface_ease': q3,
            'creative_control': q4,
            'future_use_likelihood': q5,
            'preference_match': q6,
            'ai_understanding': q7,
            'improvement_suggestions': q8
        }
        
        # 生成完整的用户数据记录
        user_data = {
            'user_info': st.session_state.user_info,
            'experiment_group': st.session_state.experiment_group,
            'design_info': st.session_state.get('design_info', None),
            'user_prompt': st.session_state.get('user_prompt', None),
            'survey_responses': st.session_state.survey_responses,
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 保存用户数据
        try:
            # 确保目录存在
            os.makedirs('data', exist_ok=True)
            
            # 生成唯一文件名
            filename = f"data/user_{int(time.time())}.json"
            
            # 保存为JSON文件
            with open(filename, 'w') as f:
                json.dump(user_data, f, indent=4)
            
            # 进入感谢页面
            st.session_state.page = "thank_you"
            st.rerun()
        except Exception as e:
            st.error(f"Error saving data: {str(e)}")

# 感谢页面
def show_thank_you_page():
    st.title("👕 Thank You!")
    st.markdown("### Your participation is greatly appreciated!")
    
    st.write("""
    Thank you for participating in our T-shirt design experiment. Your feedback 
    is invaluable and will help us improve AI-assisted design tools.
    
    Your responses have been recorded successfully.
    """)
    
    # 显示用户的最终设计（如果有）
    if 'final_design' in st.session_state and st.session_state.final_design is not None:
        st.markdown("### Your Final Design")
        st.image(st.session_state.final_design, width=300)
