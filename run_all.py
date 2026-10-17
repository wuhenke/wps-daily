# -*- coding: utf-8 -*-
"""WPS每日任务一键执行（纯API，无需浏览器/客户端）"""
import sys, os, json, re, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging
class _L:
    def __init__(s,n): pass
    def info(s,*a,**k): print("[INFO]", *a)
    def warning(s,*a,**k): print("[WARN]", *a)
    def error(s,*a,**k): print("[ERR]", *a)
    def debug(s,*a,**k): pass
    def exception(s,*a,**k): pass
import logging_utils
logging_utils.configure_logging = lambda *a,**k: None
logging_utils.get_logger = lambda *a,**k: _L("x")
logging_utils.bind_logger = lambda l,**k: l
logging_utils.log_page_switch = lambda *a,**k: None
logging_utils.log_task_result = lambda *a,**k: None

from api import WPSAPI
from daily_benefits import DailyBenefitsTasks

# 从环境变量读cookie（GitHub Secrets），或本地文件
cookie_str = os.environ.get("WPS_COOKIE", "").strip()
if not cookie_str:
    COOKIE_FILE = os.path.join(os.path.dirname(__file__), "..", "wps_cookie.txt")
    with open(COOKIE_FILE, "r", encoding="utf-8") as f:
        cookie_str = f.read().strip()
user_id = int(re.search(r'uid=(\d+)', cookie_str).group(1))

ACT = "HD2025031821201822"
PAGE = "YM2025040908558269"
TASK_COMP = "ZJ2025040709458367"
TASK_NODE = "FN1744160180RthG"

# 跳过的任务类型/ID：第三方APP、付费、邀请、学生认证、桌面端
SKIP_IDS = {266, 242, 183, 178, 39, 40, 8, 271, 272, 2, 33, 246}
# 注：272/2/33/246 今天已手动领过，后续每天需要重领（每日重置），这里只写死今天的

print("="*50)
print("【1. 任务中心签到】")
api = WPSAPI(cookie_str)
r = api.sign_in(user_id)
print("签到:", r.get('message','成功') if r.get('success') else r.get('error'))

info = api.get_user_info(ACT, PAGE)
print(f"当前积分: {info.get('points')}  九宫格剩余: {info.get('lottery_times')}次")

print("\n【2. 任务中心做任务领奖】")
# 先拉任务列表
hdr = {'User-Agent':'Mozilla/5.0','Content-Type':'application/json','Cookie':cookie_str,
       'origin':'https://personal-act.wps.cn','referer':f'https://personal-act.wps.cn/rubik2/portal/{ACT}/{PAGE}'}
r = requests.get(f'https://personal-act.wps.cn/activity-rubik/activity/page_info?activity_number={ACT}&page_number={PAGE}&filter_params=%7B%7D', headers=hdr, timeout=30)
data = r.json()
task_list = []
for item in data.get('data',[]):
    if item.get('type')==35:
        task_list = item.get('task_center',{}).get('task_list',[])
        TASK_COMP = item.get('number')
        TASK_NODE = item.get('component_node_id')
        break

done_tasks = 0
for t in task_list:
    tid = t['task_id']
    title = t.get('title','')
    event = t.get('task_event','')
    # 跳过类型：第三方APP、付费、邀请、认证、桌面端
    if event in ('exchange_traffic','trade','invite','auth','desktop_visit','desktop_install'):
        continue
    # 先 finish 标记完成，再 reward 领奖
    for action in ["task_center.finish", "task_center.reward"]:
        body = {"component_uniq_number":{"activity_number":ACT,"page_number":PAGE,
                "component_number":TASK_COMP,"component_node_id":TASK_NODE,"filter_params":{}},
                "component_type":35,"component_action":action,"task_center":{"task_id":tid}}
        resp = requests.post('https://personal-act.wps.cn/activity-rubik/activity/component_action',
                             headers=hdr, json=body, timeout=30)
        result = resp.json().get('result')
    done_tasks += 1
    print(f"  ✅ id={tid} {title} (finish+reward={result})")
print(f"共完成 {done_tasks} 个任务")

# 重新查积分和抽奖
info = api.get_user_info(ACT, PAGE)
print(f"\n任务后积分: {info.get('points')}  九宫格剩余: {info.get('lottery_times')}次")

print("\n【3. 九宫格抽奖】")
for i in range(info.get('lottery_times',0)):
    r = api.lottery(ACT, PAGE, info.get('lottery_component_number',''), info.get('lottery_component_node_id',''))
    print(f"  第{i+1}次: {r.get('prize_name', r.get('error'))}")

print("\n【4. 福利中心（打卡/试用/天天抽奖）】")
tasks = DailyBenefitsTasks(load_accounts=False, enable_notification=False)
result = tasks.process_account({"account_name":"老丁","user_id":user_id,"cookies":cookie_str,"max_lottery_limit":10})
fb = result.get("free_member_checkin",{})
print(f"打卡: {fb.get('message','')}")
mt = result.get("member_trial",{})
print(f"试用: {mt.get('message','')}")
dl = result.get("daily_lottery",{})
for a in dl.get("attempts",[]):
    print(f"  天天抽奖{a['index']}: {a.get('reward_name')}")

# 最终积分
info = api.get_user_info(ACT, PAGE)
print(f"\n最终积分: {info.get('points')}")
print("="*50)
print("全部完成")
