import streamlit as st
import os
import io
import requests
import base64
import zipfile
import time
from PIL import Image
from dotenv import load_dotenv

# 加载本地密码本
load_dotenv()

# ================= 强制网络直连防线 =================
# 屏蔽系统的 VPN/代理软件干扰，防止 ProxyError
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['NO_PROXY'] = '*'
# ==================================================

# ================= 页面全局配置 =================
st.set_page_config(page_title="AI 视觉批处理工作台", layout="wide")
st.title("🎨 电商视觉自动化工作台 (终极双擎版)")

# ================= 左侧：侧边栏控制台 =================
with st.sidebar:
    st.header("⚙️ 参数控制面板")
    
    # 自动读取 .env 里的密钥
    api_key = st.text_input("🔑 API Key", value=os.getenv("API_KEY", ""), type="password")
    
    st.subheader("0. 核心渲染引擎选择")
    engine_choice = st.radio(
        "切换底层大模型协议", 
        [
            "⚡ Gemini 原生引擎 (Gemini 3 Pro Image Preview-07)", 
            "🚀 OpenAI 兼容引擎 (gpt-image-2-9)"
        ]
    )
    
    st.subheader("1. 输出尺寸控制")
    col1, col2 = st.columns(2)
    with col1:
        target_width = st.number_input("宽度 (px)", min_value=100, max_value=4000, value=1024)
    with col2:
        target_height = st.number_input("高度 (px)", min_value=100, max_value=4000, value=1024)
        
    st.subheader("2. AI 介入程度 (模式选择)")
    mode = st.radio(
        "选择处理模式", 
        ["精修换背景 (严格保留原商品不变)", "完全重新生成 (风格创意迁移)"]
    )
    
    st.subheader("3. 画面文字控制")
    text_control = st.selectbox(
        "选择对画面中文字的约束",
        [
            "纯英文输出 (严禁中文字符，适合大马/欧美市场)", 
            "完全由提示词决定 (灵活多语言/跟随 Prompt)", 
            "画面纯净无文字 (纯净商品图，适合后期加字)"
        ]
    )
    
    st.subheader("4. 画面提示词")
    user_prompt = st.text_area(
        "输入你想在画面中增加的内容（纯描述即可）", 
        "例如：A cute dog sitting in a bright tropical living room, sunlight, high quality"
    )

# ================= 右侧：主界面操作区 =================
# 🌟 新增：为最终的压缩包开辟一个专属的“记忆保险箱”
if "final_zip" not in st.session_state:
    st.session_state.final_zip = None

uploaded_files = st.file_uploader(
    "📂 批量上传实拍原图 (支持多选)", 
    type=["png", "jpg", "jpeg"], 
    accept_multiple_files=True
)

# ================= 右侧：双按钮引擎启动区 =================
col1, col2 = st.columns(2)
with col1:
    start_fast = st.button("🚀 极速批量引擎 (火力全开)", type="primary", use_container_width=True)
with col2:
    start_slow = st.button("⏳ 防封排队引擎 (间隔10秒)", type="secondary", use_container_width=True)

# 只要按了任何一个按钮，就触发后续逻辑
if start_fast or start_slow:
    # 🌟 新增防伪补丁：点击开始的瞬间，立刻销毁上一次的下载包！
    st.session_state.final_zip = None

    if not api_key:
        st.error("请在左侧填入 API Key！")
    elif not uploaded_files:
        st.warning("请至少上传一张原图！")
    elif not user_prompt:
        st.warning("请填写画面提示词！")
    else:
        # 构建动态指令防线
        if "精修换背景" in mode:
            mode_instruction = "Keep the main subject (pet and clothing) exactly the same, only change the background to: "
        else:
            mode_instruction = "Regenerate a new creative image in the style of: "
            
        if "纯英文输出" in text_control:
            lang_lock = ", 100% English text only, absolutely NO Chinese characters, clean layout."
        elif "纯净无文字" in text_control:
            lang_lock = ", absolutely NO text, NO letters, NO words, NO watermarks, clean background."
        else:
            lang_lock = ""
            
        final_prompt = f"{mode_instruction}{user_prompt}{lang_lock}"
        
        progress_text = "引擎运转中..."
        my_bar = st.progress(0, text=progress_text)
        processed_images = []
        
        for i, file in enumerate(uploaded_files):
            current_engine_name = engine_choice.split('(')[1].replace(')', '')
            st.write(f"🔄 正在通过 **{current_engine_name}** 渲染: {file.name}...")
            
            try:
                # 降本防线：发送前拦截并压缩原图
                raw_image = Image.open(io.BytesIO(file.getvalue()))
                if raw_image.mode in ("RGBA", "P"):
                    raw_image = raw_image.convert("RGB")
                
                raw_image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                temp_buffer = io.BytesIO()
                raw_image.save(temp_buffer, format="JPEG", quality=85)
                
                encoded_string = base64.b64encode(temp_buffer.getvalue()).decode('utf-8')
                mime_type = "image/jpeg"
                
                img_data = None
                
                # 核心分流器
                if "Gemini" in engine_choice:
                    url = "https://api.tkhub.ai/v1beta/models/Gemini 3 Pro Image Preview-07:generateContent"
                    headers = {
                        "Authorization": f"Bearer {api_key}", 
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "contents": [{
                            "parts": [
                                {"text": final_prompt},
                                {"inlineData": {"mimeType": mime_type, "data": encoded_string}}
                            ]
                        }]
                    }
                    response = requests.post(url, headers=headers, json=payload)
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        candidates = response_data.get('candidates', [])
                        if candidates:
                            parts = candidates[0]['content']['parts']
                            for part in parts:
                                if 'inlineData' in part:
                                    img_data = base64.b64decode(part['inlineData']['data'])
                                elif 'text' in part and "base64," in part['text']:
                                    b64_string = part['text'].split("base64,")[1].split(")")[0].strip()
                                    img_data = base64.b64decode(b64_string)
                    else:
                        st.error(f"❌ {file.name} Gemini 接口报错: {response.text}")
                        
                else:
                    url = "https://api.tkhub.ai/v1/images/edits"
                    headers = {"Authorization": f"Bearer {api_key}"}
                    data_payload = {
                        "model": "gpt-image-2-9",
                        "prompt": final_prompt,
                        "n": 1,
                    }
                    files_payload = {
                        "image": (file.name, temp_buffer.getvalue(), mime_type)
                    }
                    response = requests.post(url, headers=headers, data=data_payload, files=files_payload)
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        if 'data' in response_data and len(response_data['data']) > 0:
                            result_item = response_data['data'][0]
                            if 'b64_json' in result_item:
                                img_data = base64.b64decode(result_item['b64_json'])
                            elif 'url' in result_item:
                                img_data = requests.get(result_item['url']).content
                    else:
                        st.error(f"❌ {file.name} OpenAI 接口报错: HTTP {response.status_code} - {response.text}")
                        
                # 品控与落盘
                if img_data:
                    image = Image.open(io.BytesIO(img_data))
                    if image.mode in ("RGBA", "P"):
                        image = image.convert("RGB")
                        
                    resized_img = Image.new("RGB", (target_width, target_height), (255, 255, 255))
                    image.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
                    paste_x = (target_width - image.width) // 2
                    paste_y = (target_height - image.height) // 2
                    resized_img.paste(image, (paste_x, paste_y))
                    
                    output_buffer = io.BytesIO()
                    quality = 95
                    while True:
                        output_buffer.seek(0)
                        output_buffer.truncate()
                        resized_img.save(output_buffer, format="JPEG", quality=quality)
                        if (len(output_buffer.getvalue()) / 1024) <= 2000 or quality <= 20:
                            break
                        quality -= 5
                        
                    original_name = os.path.splitext(file.name)[0]
                    processed_images.append({
                        "name": f"processed_{original_name}.jpg",
                        "data": output_buffer.getvalue()
                    })
                    st.success(f"✅ {file.name} 渲染完成！")
                else:
                    if response.status_code == 200: # 只有接口通了但没拿到图才报这个错，免得和上面的报错重复
                        st.error(f"❌ {file.name} 图像数据提取失败，请检查中转站返回格式。")
                    
            except Exception as e:
                st.error(f"处理 {file.name} 时发生系统错误: {e}")
                
            # 步进刷新进度条
            my_bar.progress((i + 1) / len(uploaded_files), text=f"整体进度: {i+1}/{len(uploaded_files)}")
            
            # ================= 🌟 核心防封禁排队逻辑 =================
            # 如果点了慢速引擎，且当前不是最后一张图片，就强制倒计时 10 秒
            if start_slow and i < len(uploaded_files) - 1:
                countdown_placeholder = st.empty() # 创建一个占位符
                for sec in range(10, 0, -1):
                    countdown_placeholder.warning(f"⏳ 慢速排队模式启动：为防止接口过载封禁，系统将在 {sec} 秒后处理下一张...")
                    time.sleep(1) # 暂停1秒
                countdown_placeholder.empty() # 倒计时结束，悄悄清空这行提示语
            # =======================================================
            
# ================= 渲染完毕，将结果存入保险箱 =================
        if processed_images:
            st.balloons() 
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for img in processed_images:
                    zip_file.writestr(img["name"], img["data"])
                    
            # 🌟 关键动作：把打包好的文件流存入记忆中，不再直接渲染按钮
            st.session_state.final_zip = zip_buffer.getvalue()

# ================= 独立保护区：永不闪退的下载按钮 =================
# ⚠️ 注意缩进：这段代码必须【顶格】或只缩进在没有任何 if 条件的外部！
# 也就是说，它与最外层的 `if start_fast or start_slow:` 是平级的兄弟关系。

if st.session_state.final_zip:
    st.write("---")
    st.success("🎉 所有图片已处理完毕并打包就绪！")
    st.download_button(
        label="📦 一键打包下载全部产出 (ZIP文件)",
        data=st.session_state.final_zip,
        file_name="AI_Commerce_Assets.zip",
        mime="application/zip",
        type="primary",
        use_container_width=True
    )