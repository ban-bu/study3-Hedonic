import streamlit as st
from PIL import Image, ImageDraw
import requests
from io import BytesIO
import os  # 确保os模块在这里导入
# 移除cairosvg依赖，使用svglib作为唯一的SVG处理库
try:
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
    SVGLIB_AVAILABLE = True
except ImportError:
    SVGLIB_AVAILABLE = False
    st.warning("SVG processing libraries not installed, SVG conversion will not be available")
from openai import OpenAI
from streamlit_image_coordinates import streamlit_image_coordinates
import re
import math
# 导入面料纹理模块
from fabric_texture import apply_fabric_texture
import uuid
import json
# 导入并行处理库
import concurrent.futures
import time

# API配置信息 - 实际使用时应从主文件传入或使用环境变量
API_KEY = "sk-lNVAREVHjj386FDCd9McOL7k66DZCUkTp6IbV0u9970qqdlg"
BASE_URL = "https://api.deepbricks.ai/v1/"

# GPT-4o-mini API配置
GPT4O_MINI_API_KEY = "sk-lNVAREVHjj386FDCd9McOL7k66DZCUkTp6IbV0u9970qqdlg"
GPT4O_MINI_BASE_URL = "https://api.deepbricks.ai/v1/"

# 从svg_utils导入SVG转换函数
from svg_utils import convert_svg_to_png

# 设置默认关键词风格，取代UI上的选择按钮
DEFAULT_KEYWORD_STYLE = "hedonic"  # 可以设置为"hedonic"或"functional"

def get_design_keywords(keyword_style):
    """获取设计关键词列表"""
    if keyword_style == "hedonic":
        return [
            "Artistic", "Beautiful", "Colorful", "Elegant", "Fun",
            "Minimalist", "Modern", "Playful", "Retro", "Stylish",
            "Vibrant", "Vintage", "Bold", "Creative", "Unique",
            "Abstract", "Aesthetic", "Fashion", "Trendy", "Cool"
        ]
    else:  # functional
        return [
            "Breathable", "Comfortable", "Durable", "Eco-friendly", "Lightweight",
            "Moisture-wicking", "Practical", "Quality", "Soft", "Sturdy",
            "Versatile", "Athletic", "Casual", "Classic", "Daily",
            "Outdoor", "Performance", "Sports", "Stretchy", "Travel"
        ]

def get_ai_design_suggestions(user_preferences=None):
    """Get design suggestions from GPT-4o-mini with more personalized features"""
    client = OpenAI(api_key=GPT4O_MINI_API_KEY, base_url=GPT4O_MINI_BASE_URL)
    
    # Default prompt if no user preferences provided
    if not user_preferences:
        user_preferences = "casual fashion t-shirt design"
    
    # Construct the prompt
    prompt = f"""
    As a T-shirt design consultant, please provide personalized design suggestions for a "{user_preferences}" style T-shirt.
    
    Please provide the following design suggestions in JSON format:

    1. Color: Select the most suitable color for this style (provide name and hex code)
    2. Fabric: Select the most suitable fabric type (Cotton, Polyester, Cotton-Polyester Blend, Jersey, Linen, or Bamboo)
    3. Text: A suitable phrase or slogan that matches the style (keep it concise and impactful)
    4. Logo: A brief description of a logo/graphic element that would complement the design

    Return your response as a valid JSON object with the following structure:
    {{
        "color": {{
            "name": "Color name",
            "hex": "#XXXXXX"
        }},
        "fabric": "Fabric type",
        "text": "Suggested text or slogan",
        "logo": "Logo/graphic description"
    }}
    """
    
    try:
        # 调用GPT-4o-mini
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional T-shirt design consultant. Provide design suggestions in JSON format exactly as requested."},
                {"role": "user", "content": prompt}
            ]
        )
        
        # 返回建议内容
        if response.choices and len(response.choices) > 0:
            suggestion_text = response.choices[0].message.content
            
            # 尝试解析JSON
            try:
                # 查找JSON格式的内容
                json_match = re.search(r'```json\s*(.*?)\s*```', suggestion_text, re.DOTALL)
                if json_match:
                    suggestion_json = json.loads(json_match.group(1))
                else:
                    # 尝试直接解析整个内容
                    suggestion_json = json.loads(suggestion_text)
                
                return suggestion_json
            except Exception as e:
                print(f"Error parsing JSON: {e}")
                return {"error": f"Failed to parse design suggestions: {str(e)}"}
        else:
            return {"error": "Failed to get AI design suggestions. Please try again later."}
    except Exception as e:
        return {"error": f"Error getting AI design suggestions: {str(e)}"}

def generate_vector_image(prompt, background_color=None):
    """Generate an image based on the prompt with specified background color"""
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    
    # 如果提供了背景颜色，在提示中指定
    color_prompt = ""
    if background_color:
        color_prompt = f" with EXACT RGB background color matching {background_color}"
    
    # 添加禁止生成T恤或服装的提示
    prohibition = " DO NOT include any t-shirts, clothing, mockups, or how the design would look when applied to products. Create ONLY the standalone graphic."
    
    try:
        resp = client.images.generate(
            model="dall-e-3",
            prompt=prompt + f" (Make sure the image has a solid{color_prompt} background, NOT transparent. This is very important for my design!){prohibition}",
            n=1,
            size="1024x1024",
            quality="standard"
        )
    except Exception as e:
        st.error(f"Error calling API: {e}")
        return None, {"error": f"Error calling API: {e}"}

    if resp and len(resp.data) > 0 and resp.data[0].url:
        image_url = resp.data[0].url
        try:
            image_resp = requests.get(image_url)
            if image_resp.status_code == 200:
                content_type = image_resp.headers.get("Content-Type", "")
                if "svg" in content_type.lower():
                    # 使用集中的SVG处理函数
                    image = convert_svg_to_png(image_resp.content)
                    return image, {"prompt": prompt, "image_url": image_url}
                else:
                    # 确保图像没有透明背景，使用指定的背景色
                    img = Image.open(BytesIO(image_resp.content)).convert("RGBA")
                    
                    # 如果提供了背景颜色，使用指定颜色；否则使用白色
                    if background_color:
                        # 转换十六进制颜色为RGB
                        bg_color = tuple(int(background_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + (255,)
                    else:
                        bg_color = (255, 255, 255, 255)
                    
                    # 创建指定背景色的背景图像
                    color_bg = Image.new("RGBA", img.size, bg_color)
                    # 合成图像，消除透明度
                    img = Image.alpha_composite(color_bg, img)
                    return img, {"prompt": prompt, "image_url": image_url}
            else:
                st.error(f"Failed to download image, status code: {image_resp.status_code}")
        except Exception as download_err:
            st.error(f"Error requesting image: {download_err}")
    else:
        st.error("Could not get image URL from API response.")
    return None, {"error": "Failed to generate or download image"}

def change_shirt_color(image, color_hex, apply_texture=False, fabric_type=None):
    """Change T-shirt color with optional fabric texture"""
    # 转换十六进制颜色为RGB
    color_rgb = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    
    # 创建副本避免修改原图
    colored_image = image.copy().convert("RGBA")
    
    # 获取图像数据
    data = colored_image.getdata()
    
    # 创建新数据
    new_data = []
    # 白色阈值 - 调整这个值可以控制哪些像素被视为白色/浅色并被改变
    threshold = 200
    
    for item in data:
        # 判断是否是白色/浅色区域 (RGB值都很高)
        if item[0] > threshold and item[1] > threshold and item[2] > threshold and item[3] > 0:
            # 保持原透明度，改变颜色
            new_color = (color_rgb[0], color_rgb[1], color_rgb[2], item[3])
            new_data.append(new_color)
        else:
            # 保持其他颜色不变
            new_data.append(item)
    
    # 更新图像数据
    colored_image.putdata(new_data)
    
    # 如果需要应用纹理
    if apply_texture and fabric_type:
        return apply_fabric_texture(colored_image, fabric_type)
    
    return colored_image

def apply_text_to_shirt(image, text, color_hex="#FFFFFF", font_size=80):
    """Apply text to T-shirt image"""
    if not text:
        return image
    
    # 创建副本避免修改原图
    result_image = image.copy().convert("RGBA")
    img_width, img_height = result_image.size
    
    # 创建透明的文本图层
    text_layer = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)
    
    # 尝试加载字体
    from PIL import ImageFont
    import platform
    
    font = None
    try:
        system = platform.system()
        
        # 根据不同系统尝试不同的字体路径
        if system == 'Windows':
            font_paths = [
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/ARIAL.TTF",
                "C:/Windows/Fonts/calibri.ttf",
            ]
        elif system == 'Darwin':  # macOS
            font_paths = [
                "/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ]
        else:  # Linux或其他
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            ]
        
        # 尝试加载每个字体
        for font_path in font_paths:
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, font_size)
                break
    except Exception as e:
        print(f"Error loading font: {e}")
    
    # 如果加载失败，使用默认字体
    if font is None:
        try:
            font = ImageFont.load_default()
        except:
            print("Could not load default font")
            return result_image
    
    # 将十六进制颜色转换为RGB
    color_rgb = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    text_color = color_rgb + (255,)  # 添加不透明度
    
    # 计算文本位置 (居中)
    text_bbox = text_draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    text_x = (img_width - text_width) // 2
    text_y = (img_height // 3) - (text_height // 2)  # 放在T恤上部位置
    
    # 绘制文本
    text_draw.text((text_x, text_y), text, fill=text_color, font=font)
    
    # 组合图像
    result_image = Image.alpha_composite(result_image, text_layer)
    
    return result_image

def apply_logo_to_shirt(shirt_image, logo_image, position="center", size_percent=60, background_color=None):
    """Apply logo to T-shirt image with better blending to reduce shadows"""
    if logo_image is None:
        return shirt_image
    
    # 创建副本避免修改原图
    result_image = shirt_image.copy().convert("RGBA")
    img_width, img_height = result_image.size
    
    # 定义T恤前胸区域
    chest_width = int(img_width * 0.95)
    chest_height = int(img_height * 0.6)
    chest_left = (img_width - chest_width) // 2
    chest_top = int(img_height * 0.2)
    
    # 提取logo前景
    logo_with_bg = logo_image.copy().convert("RGBA")
    
    # 调整Logo大小
    logo_size_factor = size_percent / 100
    logo_width = int(chest_width * logo_size_factor * 0.7)
    logo_height = int(logo_width * logo_with_bg.height / logo_with_bg.width)
    logo_resized = logo_with_bg.resize((logo_width, logo_height), Image.LANCZOS)
    
    # 根据位置确定坐标
    position = position.lower() if isinstance(position, str) else "center"
    
    if position == "top-center":
        logo_x, logo_y = chest_left + (chest_width - logo_width) // 2, chest_top + 10
    elif position == "center":
        logo_x, logo_y = chest_left + (chest_width - logo_width) // 2, chest_top + (chest_height - logo_height) // 2 + 30  # 略微偏下
    else:  # 默认中间
        logo_x, logo_y = chest_left + (chest_width - logo_width) // 2, chest_top + (chest_height - logo_height) // 2 + 30
    
    # 创建一个蒙版，用于混合logo和T恤
    # 提取logo的非背景部分
    logo_mask = Image.new("L", logo_resized.size, 0)  # 创建一个黑色蒙版（透明）
    
    # 如果提供了背景颜色，使用它来判断什么是背景
    if background_color:
        bg_color_rgb = tuple(int(background_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    else:
        # 默认假设白色是背景
        bg_color_rgb = (255, 255, 255)
    
    # 遍历像素，创建蒙版
    for y in range(logo_resized.height):
        for x in range(logo_resized.width):
            pixel = logo_resized.getpixel((x, y))
            if len(pixel) >= 3:  # 至少有RGB值
                # 计算与背景颜色的差异
                r_diff = abs(pixel[0] - bg_color_rgb[0])
                g_diff = abs(pixel[1] - bg_color_rgb[1])
                b_diff = abs(pixel[2] - bg_color_rgb[2])
                diff = r_diff + g_diff + b_diff
                
                # 如果差异大于阈值，则认为是前景
                if diff > 60:  # 可以调整阈值
                    # 根据差异程度设置不同的透明度
                    transparency = min(255, diff)
                    logo_mask.putpixel((x, y), transparency)
    
    # 获取logo区域在T恤上的背景图像
    shirt_region = result_image.crop((logo_x, logo_y, logo_x + logo_width, logo_y + logo_height))
    
    # 合成logo和T恤区域，使用蒙版确保只有logo的非背景部分被使用
    # 这样能够保留T恤的原始纹理
    for y in range(logo_height):
        for x in range(logo_width):
            mask_value = logo_mask.getpixel((x, y))
            if mask_value > 20:  # 有一定的不透明度
                # 获取logo像素
                logo_pixel = logo_resized.getpixel((x, y))
                # 获取T恤对应位置的像素
                shirt_pixel = shirt_region.getpixel((x, y))
                
                # 根据透明度混合像素
                alpha = mask_value / 255.0
                blended_pixel = (
                    int(logo_pixel[0] * alpha + shirt_pixel[0] * (1 - alpha)),
                    int(logo_pixel[1] * alpha + shirt_pixel[1] * (1 - alpha)),
                    int(logo_pixel[2] * alpha + shirt_pixel[2] * (1 - alpha)),
                    255  # 完全不透明
                )
                
                # 更新T恤区域的像素
                shirt_region.putpixel((x, y), blended_pixel)
    
    # 将修改后的区域粘贴回T恤
    result_image.paste(shirt_region, (logo_x, logo_y))
    
    return result_image

def generate_complete_design(design_prompt, variation_id=None):
    """Generate complete T-shirt design based on prompt"""
    if not design_prompt:
        return None, {"error": "Please enter a design prompt"}
    
    # 获取AI设计建议
    design_suggestions = get_ai_design_suggestions(design_prompt)
    
    if "error" in design_suggestions:
        return None, design_suggestions
    
    # 加载原始T恤图像
    try:
        original_image_path = "white_shirt.png"
        possible_paths = [
            "white_shirt.png",
            "./white_shirt.png",
            "../white_shirt.png",
            "images/white_shirt.png",
        ]
        
        found = False
        for path in possible_paths:
            if os.path.exists(path):
                original_image_path = path
                found = True
                break
        
        if not found:
            return None, {"error": "Could not find base T-shirt image"}
        
        # 加载原始白色T恤图像
        original_image = Image.open(original_image_path).convert("RGBA")
    except Exception as e:
        return None, {"error": f"Error loading T-shirt image: {str(e)}"}
    
    try:
        # 如果提供了变体ID，为不同变体生成不同的设计
        color_hex = design_suggestions.get("color", {}).get("hex", "#FFFFFF")
        fabric_type = design_suggestions.get("fabric", "Cotton")
        
        # 根据变体ID调整颜色和纹理
        if variation_id is not None:
            # 为不同变体生成不同的颜色 (简单的色调变化)
            color_rgb = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            r, g, b = color_rgb
            
            if variation_id == 1:  # 稍微调亮
                r = min(255, int(r * 1.2))
                g = min(255, int(g * 1.2))
                b = min(255, int(b * 1.2))
            elif variation_id == 2:  # 稍微调暗
                r = int(r * 0.8)
                g = int(g * 0.8)
                b = int(b * 0.8)
            elif variation_id == 3:  # 更偏向红色
                r = min(255, int(r * 1.3))
            elif variation_id == 4:  # 更偏向蓝色
                b = min(255, int(b * 1.3))
            
            color_hex = f"#{r:02x}{g:02x}{b:02x}"
            
            # 可能的面料变化
            fabric_options = ["Cotton", "Polyester", "Cotton-Polyester Blend", "Jersey", "Linen", "Bamboo"]
            if variation_id < len(fabric_options):
                fabric_type = fabric_options[variation_id % len(fabric_options)]
        
        # 1. 应用颜色和纹理
        colored_shirt = change_shirt_color(
            original_image,
            color_hex,
            apply_texture=True,
            fabric_type=fabric_type
        )
        
        # 2. 生成Logo
        logo_description = design_suggestions.get("logo", "")
        logo_image = None
        
        if logo_description:
            # 为变体版本可能稍微修改logo描述
            logo_desc = logo_description
            if variation_id is not None and variation_id > 0:
                modifiers = ["minimalist", "colorful", "abstract", "geometric", "vintage"]
                if variation_id <= len(modifiers):
                    logo_desc = f"{modifiers[variation_id-1]} {logo_description}"
            
            # 修改Logo提示词，确保生成的Logo有与T恤颜色相匹配的背景，并且不会包含T恤图像
            logo_prompt = f"""Create a Logo design for printing: {logo_desc}. 
            Requirements: 
            1. Simple professional design
            2. Solid background color matching the t-shirt
            3. Clear and distinct graphic
            4. Good contrast with colors that will show well on fabric
            5. IMPORTANT: Do NOT include any t-shirts, clothing, or apparel in the design
            6. IMPORTANT: Do NOT include any mockups or product previews
            7. IMPORTANT: Create ONLY the logo graphic itself, NOT how it would look on a t-shirt
            8. NO META REFERENCES - do not show the logo applied to anything
            9. Design should be a standalone graphic symbol/icon only"""
            
            logo_image, logo_info = generate_vector_image(logo_prompt, color_hex)
        
        # 最终设计 - 不添加文字
        final_design = colored_shirt
        
        # 应用Logo (如果有)
        if logo_image:
            # 使用与T恤相同的颜色作为logo背景
            final_design = apply_logo_to_shirt(colored_shirt, logo_image, "center", 60, color_hex)
        
        return final_design, {
            "color": {"hex": color_hex, "name": design_suggestions.get("color", {}).get("name", "Custom Color")},
            "fabric": fabric_type,
            "logo": logo_description,
            "variation_id": variation_id
        }
    
    except Exception as e:
        import traceback
        traceback_str = traceback.format_exc()
        return None, {"error": f"Error generating design: {str(e)}\n{traceback_str}"}

def generate_multiple_designs(design_prompt, count=1):
    """Generate multiple T-shirt designs in parallel"""
    if count <= 1:
        # 如果只需要一个设计，直接生成不需要并行
        base_design, base_info = generate_complete_design(design_prompt)
        if base_design:
            return [(base_design, base_info)]
        else:
            return []
    
    designs = []
    
    # 定义一个函数来生成单个设计，用于并行处理
    def generate_single_design(variation_id):
        try:
            if variation_id == 0:  # 基础设计
                return generate_complete_design(design_prompt)
            else:  # 变体设计
                return generate_complete_design(design_prompt, variation_id=variation_id)
        except Exception as e:
            print(f"Error generating design {variation_id}: {e}")
            return None, {"error": f"Failed to generate design {variation_id}"}
    
    # 创建线程池
    with concurrent.futures.ThreadPoolExecutor(max_workers=count) as executor:
        # 提交所有任务
        future_to_id = {executor.submit(generate_single_design, i): i for i in range(count)}
        
        # 收集结果
        for future in concurrent.futures.as_completed(future_to_id):
            design_id = future_to_id[future]
            try:
                design, info = future.result()
                if design:
                    designs.append((design, info))
            except Exception as e:
                print(f"Design {design_id} generated an exception: {e}")
    
    # 按照原始ID顺序排序
    designs.sort(key=lambda x: x[1].get("variation_id", 0) if x[1] and "variation_id" in x[1] else 0)
    
    return designs

def show_low_recommendation_without_explanation():
    st.title("👕 AI Recommendation Experiment Platform")
    st.markdown("### Study3-Let AI Design Your T-shirt")
    
    # 显示实验组和关键词风格信息
    if DEFAULT_KEYWORD_STYLE == "hedonic":
        style_text = "Hedonic (aesthetics and emotions)"
    else:
        style_text = "Functional (practical features)"
    
    st.info(f"You are currently in Study3, and the keyword style is set to {style_text}")
    
    # 添加提示信息
    st.markdown("""
    <div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px; margin-bottom: 20px;">
    <p style="margin: 0; font-size: 16px;">Please generate a T-shirt design based on the following keywords. After selecting a few keywords, click the "Generate T-shirt Design" button to automatically generate a T-shirt design. After generation, you can download or confirm the design.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 初始化会话状态变量
    if 'user_prompt' not in st.session_state:
        st.session_state.user_prompt = ""
    if 'final_design' not in st.session_state:
        st.session_state.final_design = None
    if 'design_info' not in st.session_state:
        st.session_state.design_info = None
    if 'is_generating' not in st.session_state:
        st.session_state.is_generating = False
    if 'should_generate' not in st.session_state:
        st.session_state.should_generate = False
    if 'keyword_style' not in st.session_state:
        # 设置固定关键词风格，不再允许用户选择
        st.session_state.keyword_style = DEFAULT_KEYWORD_STYLE
    if 'generated_designs' not in st.session_state:
        st.session_state.generated_designs = []
    if 'selected_design_index' not in st.session_state:
        st.session_state.selected_design_index = 0
    if 'original_tshirt' not in st.session_state:
        # 加载原始白色T恤图像
        try:
            original_image_path = "white_shirt.png"
            possible_paths = [
                "white_shirt.png",
                "./white_shirt.png",
                "../white_shirt.png",
                "images/white_shirt.png",
            ]
            
            found = False
            for path in possible_paths:
                if os.path.exists(path):
                    original_image_path = path
                    found = True
                    break
            
            if found:
                st.session_state.original_tshirt = Image.open(original_image_path).convert("RGBA")
            else:
                st.error("Could not find base T-shirt image")
                st.session_state.original_tshirt = None
        except Exception as e:
            st.error(f"Error loading T-shirt image: {str(e)}")
            st.session_state.original_tshirt = None

    # 移除选项卡，直接使用默认风格
    keywords = get_design_keywords(st.session_state.keyword_style)
    
    col1, col2 = st.columns([2, 3])
    
    with col1:
        st.subheader("Select Keywords")
        
        # 关键词多选
        selected_keywords = st.multiselect(
            "Choose keywords for your design:",
            options=keywords,
            default=[],
            key="keyword_selector"
        )
        
        # 用户自定义提示词输入
        st.text_area(
            "Add your own description (optional):",
            key="custom_description",
            height=100,
            help="Add any additional details you want in your design"
        )
        
        # 生成按钮
        generate_pressed = st.button(
            "🎨 Generate T-shirt Design", 
            key="generate_btn",
            type="primary",
            disabled=st.session_state.is_generating or len(selected_keywords) == 0
        )
        
        if generate_pressed:
            st.session_state.should_generate = True
            st.session_state.is_generating = True
            st.rerun()
            
    # 右侧显示生成结果
    with col2:
        st.subheader("Your Design")
        
        # 处理生成的请求
        if st.session_state.should_generate:
            with st.spinner("AI is designing your T-shirt..."):
                # 构建提示词
                prompt = ", ".join(st.session_state.keyword_selector)
                if st.session_state.custom_description.strip():
                    prompt += f". {st.session_state.custom_description.strip()}"
                
                st.session_state.user_prompt = prompt
                
                # 获取设计建议
                design_suggestions = get_ai_design_suggestions(prompt)
                
                # 生成设计
                generated_designs = []
                # 修改为直接处理单个设计建议字典，使用generate_complete_design函数
                if "error" not in design_suggestions:
                    # 使用与high_no_explanation相同的生成机制
                    design_img, design_info = generate_complete_design(prompt)
                    
                    if design_img:
                        generated_designs.append({
                            "image": design_img,
                            "info": design_info,
                            "suggestion": design_suggestions
                        })
                
                st.session_state.generated_designs = generated_designs
                if generated_designs:
                    st.session_state.final_design = generated_designs[0]["image"]
                    st.session_state.design_info = generated_designs[0]["info"]
                
                st.session_state.should_generate = False
                st.session_state.is_generating = False
                st.rerun()
        
        # 显示生成的设计
        if st.session_state.generated_designs:
            # 如果有多个设计，显示一个选择器
            if len(st.session_state.generated_designs) > 1:
                design_options = [f"Design {i+1}" for i in range(len(st.session_state.generated_designs))]
                selected_design = st.radio(
                    "Choose a design:",
                    options=design_options,
                    index=st.session_state.selected_design_index,
                    horizontal=True,
                    key="design_selector"
                )
                selected_index = design_options.index(selected_design)
                
                if selected_index != st.session_state.selected_design_index:
                    st.session_state.selected_design_index = selected_index
                    st.session_state.final_design = st.session_state.generated_designs[selected_index]["image"]
                    st.session_state.design_info = st.session_state.generated_designs[selected_index]["info"]
                    st.rerun()
            
            # 显示当前选中的设计
            if st.session_state.final_design is not None:
                st.image(
                    st.session_state.final_design,
                    caption=f"Your T-shirt Design",
                    use_column_width=True
                )
                
                # 显示设计描述
                if st.session_state.design_info:
                    with st.expander("Design Details", expanded=False):
                        st.write(st.session_state.design_info)
        else:
            # 显示提示信息
            st.info("Select keywords and click 'Generate T-shirt Design' to create your custom T-shirt")
    
    # 下载按钮 (在主区域底部)
    if st.session_state.final_design is not None:
        st.markdown("---")
        # 将两列布局改为单列
        # download_col, next_col = st.columns(2)
        
        # 直接显示下载按钮，不使用列布局
        buf = BytesIO()
        st.session_state.final_design.save(buf, format="PNG")
        buf.seek(0)
        st.download_button(
            label="💾 下载设计图",
            data=buf,
            file_name="ai_tshirt_design.png",
            mime="image/png",
            use_container_width=True  # 使按钮占据整个宽度
        )
        
        # 移除确认按钮和问卷相关功能
        # with next_col:
        #     # 确认完成按钮
        #     if st.button("✅ Confirm"):
        #         st.session_state.page = "survey"
        #         st.rerun()
