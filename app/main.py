import os
import time
import random
import yaml
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# --- 加载 YAML 配置 ---
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"未找到配置文件: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

config = load_config()

# 提取配置
HALO_BASE_URL = config['halo']['base_url'].rstrip('/')
TOKEN = config['halo']['token']
VIDEO_GROUP = config['halo']['video_group_id']
CACHE_TTL = config['server'].get('cache_ttl', 600)
LISTEN_PORT = config['server'].get('port', 80)

# 附件查询接口
HALO_API_ATTACHMENT_URL = f"{HALO_BASE_URL}/apis/api.console.halo.run/v1alpha1/attachments"

# 内存缓存
cache = {
    "items": [],
    "last_updated": 0
}

def fetch_video_list():
    headers = {"Authorization": f"Bearer {TOKEN}"}
    params = {
        "fieldSelector": f"spec.groupName={VIDEO_GROUP}",
        "accepts": "video/*",
        "size": 100
    }
    try:
        r = requests.get(HALO_API_ATTACHMENT_URL, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        print(f"❌ 抓取数据失败: {e}")
        return []

@app.get("/api/v1/random-video")
def get_random_video():
    """
    获取随机视频信息的 API 接口。

    该接口首先检查缓存是否过期，若过期则更新缓存。
    随后从缓存中随机选择一个视频，构建完整的访问 URL 并返回。

    Returns:
        dict: 包含视频标题 (title) 和完整 URL (url) 的字典。
              若发生错误，返回包含 error 键的字典。
    """
    now = time.time()
    
    # 1. 缓存更新逻辑
    if not cache["items"] or (now - cache["last_updated"] > CACHE_TTL):
        new_items = fetch_video_list()
        if new_items:
            cache["items"] = new_items
            cache["last_updated"] = now
            print(f"🔄 缓存已更新，共 {len(new_items)} 个视频")

    # 检查缓存数据是否可用
    if not cache["items"]:
        return {"error": "无法获取视频列表，请检查配置"}

    try:
        # 2. 随机选择一个视频对象
        video = random.choice(cache["items"])
        
        # 3. 按照你提供的结构精准取值
        # 视频标题
        display_name = video.get("spec", {}).get("displayName", "未命名视频")
        
        # 视频路径：从 status.permalink 获取
        permalink = video.get("status", {}).get("permalink", "")
        
        if not permalink:
            return {"error": "数据中未找到有效视频路径 (permalink)"}

        # 4. 关键：拼接完整 URL
        # 如果 permalink 是以 / 开头的相对路径，则拼接上 base_url
        full_url = permalink
        if permalink.startswith("/"):
            full_url = f"{HALO_BASE_URL}{permalink}"

        return {
            "title": display_name,
            "url": full_url
        }
    except Exception as e:
        print(f"❌ 路由逻辑报错：{e}")
        return {"error": "处理数据时发生异常", "details": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=LISTEN_PORT, ws=None)