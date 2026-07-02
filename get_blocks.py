import urllib.request
import json
import ssl
import os
import time
import gzip
import io
import configparser
from datetime import datetime

# ============================================================
# 配置读取 —— 从 config.ini 加载 (标准库 configparser，兼容 Python 2+)
# 编辑 config.ini 修改 TOKEN 和 BLOCK_LINK 即可
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.ini")

if not os.path.exists(CONFIG_PATH):
    print(f"找不到配置文件: {CONFIG_PATH}")
    print("   请将 config.ini 放在脚本同目录，并填写 TOKEN 和 BLOCK_LINK")
    exit(1)

config = configparser.ConfigParser()
config.read(CONFIG_PATH, encoding="utf-8")
cfg = config["config"]

TOKEN = cfg["TOKEN"]
BLOCK_LINK = cfg["BLOCK_LINK"]
CONTAINER_BLOCK_ID = BLOCK_LINK.split("#")[-1]
SPACE_NAME = cfg.get("SPACE_NAME", "ATE Lab Co-work")

BASE_URL = "https://note.kxsz.net"

# 将在初始化时自动获取
uid = None
space_id = None

ctx = ssl.create_default_context()

def make_headers(referer="/"):
    return {
        "authority": "note.kxsz.net",
        "accept": "application/json, text/plain, */*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "zh-CN,zh;q=0.9",
        "authorization": f"Bearer {TOKEN}",
        "origin": "https://note.kxsz.net",
        "referer": f"https://note.kxsz.net{referer}",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "content-type": "application/json; charset=UTF-8"
    }

def decode_response(resp):
    raw = resp.read()
    content_encoding = resp.headers.get("Content-Encoding", "")
    if "gzip" in content_encoding:
        buf = io.BytesIO(raw)
        with gzip.GzipFile(fileobj=buf) as f:
            raw = f.read()
    return json.loads(raw.decode("utf-8"))

def api_get(path):
    """调用 API GET 请求"""
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers=make_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            return decode_response(resp)
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.reason}")
        return None

def api_post(path, body_dict, referer="/"):
    url = f"{BASE_URL}{path}"
    data = json.dumps(body_dict, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=make_headers(referer), method="POST")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return decode_response(resp)
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.reason}")
        return None

# ============================================================
# 初始化：自动获取 uid + space_id
# ============================================================
print("=" * 60)
print("初始化...")

# 1. 获取 uid
print("  获取用户信息...")
user_info = api_get("/api/user/getUserInfo")
if user_info and user_info.get("code") == 0:
    uid = user_info["data"]["unionid"]
    print(f"  uid: {uid} (用户: {user_info['data']['nickname']})")
else:
    print("  获取用户信息失败!")
    exit(1)

# 2. 获取 space_id
print("  获取团队空间列表...")
team_list = api_get("/api/note/team/list")
if team_list and team_list.get("code") == 0:
    for team in team_list["data"]["list"]:
        if team["name"] == SPACE_NAME:
            space_id = team["space_id"]
            print(f"  space_id: {space_id} (空间: {SPACE_NAME})")
            break
if not space_id:
    print(f"  未找到空间 \"{SPACE_NAME}\"!")
    exit(1)

# ============================================================
# 主流程
# ============================================================
def get_block_list(block_ids):
    body = {
        "list": block_ids,
        "space_id": space_id,
        "uid": uid,
        "token": TOKEN
    }
    return api_post("/api/note/block/list", body)

def get_block_detail(block_id):
    result = get_block_list([block_id])
    if result and result.get("data") and result["data"].get("block_map"):
        return result["data"]["block_map"].get(block_id)
    return None

def export_block_as_pdf(block_id, output_path):
    body = {
        "space_id": space_id,
        "space_name": SPACE_NAME,
        "note_id": block_id,
        "uid": uid,
        "name": f"export-{block_id[:8]}",
        "token": TOKEN,
        "waiting_time": 2000,
        "scale": 0.75,
        "type": "pdf"
    }
    result = api_post("/api/note/blockExport", body)
    if result and result.get("code") == 0:
        pdf_url = result["data"]["url"]
        pdf_req = urllib.request.Request(pdf_url, headers={"User-Agent": make_headers()["user-agent"]})
        with urllib.request.urlopen(pdf_req, context=ctx, timeout=60) as resp:
            with open(output_path, "wb") as f:
                f.write(resp.read())
        return True
    return False

def safe_filename(text, max_len=60):
    invalid = r'<>:"/\|?*'
    for c in invalid:
        text = text.replace(c, '')
    text = text.strip().replace(' ', '_')[:max_len]
    text = text.replace('\n', '').replace('\r', '')
    return text or "untitled"

def get_title(block):
    attrs = block.get("attributes", {})
    nodes = attrs.get("nodes", [])
    if nodes and len(nodes) > 0:
        return nodes[0][0] if nodes[0] else "untitled"
    return "untitled"

# --- 获取容器块信息 ---
print("\n获取容器块详情...")
result = get_block_list([CONTAINER_BLOCK_ID])
children = []
container_title = "untitled"
if result and result.get("data") and result["data"].get("block_map"):
    container = result["data"]["block_map"].get(CONTAINER_BLOCK_ID, {})
    children = container.get("blocks", [])
    container_title = get_title(container)
    print(f"  {container_title} ({len(children)} 个子块)")
else:
    print("  无法获取容器块信息")
    exit(1)

if not children:
    print("  没有子块，退出")
    exit(0)

# --- 获取子块详情 ---
print("\n子块列表:")
child_details = []
batch_result = get_block_list(children)
if batch_result and batch_result.get("data") and batch_result["data"].get("block_map"):
    sub_map = batch_result["data"]["block_map"]
    for cid in children:
        block = sub_map.get(cid, {})
        title = get_title(block)
        child_details.append((cid, title))
        print(f"  [{cid[:8]}] {title}")
        time.sleep(0.2)
else:
    for cid in children:
        block = get_block_detail(cid)
        title = get_title(block) if block else "untitled"
        child_details.append((cid, title))
        print(f"  [{cid[:8]}] {title}")
        time.sleep(0.3)

# --- 测试导出第一个子块 ---
print(f"\n测试导出: 第一个子块 ({child_details[0][1]})")
output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{safe_filename(container_title)}_pdfs")
os.makedirs(output_dir, exist_ok=True)

cid, title = child_details[0]
test_path = os.path.join(output_dir, f"01_{safe_filename(title)}.pdf")
ok = export_block_as_pdf(cid, test_path)
if ok:
    print(f"  测试成功! -> {os.path.basename(test_path)}")
else:
    print("  测试失败! 请检查 token 是否过期")
    exit(1)

# --- 导出剩余子块（跳过第一个，已在测试中导出）---
print(f"\n导出剩余 {len(child_details)-1} 个子块...")
for i, (cid, title) in enumerate(child_details[1:], start=2):
    safe_name = safe_filename(title)
    out_path = os.path.join(output_dir, f"{i:02d}_{safe_name}.pdf")
    print(f"  [{i}/{len(child_details)}] {os.path.basename(out_path)}")
    ok = export_block_as_pdf(cid, out_path)
    print(f"      {'成功' if ok else '失败'}")
    time.sleep(1)
print(f"\n完成! 文件保存在: {output_dir}")
