# -*- coding: utf-8 -*-
"""WPS姣忔棩浠诲姟涓€閿墽琛岋紙绾疉PI锛屾棤闇€娴忚鍣?瀹㈡埛绔級"""
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

# 浠庣幆澧冨彉閲忚cookie锛圙itHub Secrets锛夛紝鎴栨湰鍦版枃浠?cookie_str = os.environ.get("WPS_COOKIE", "").strip()
if not cookie_str:
    COOKIE_FILE = os.path.join(os.path.dirname(__file__), "..", "wps_cookie.txt")
    with open(COOKIE_FILE, "r", encoding="utf-8") as f:
        cookie_str = f.read().strip()
user_id = int(re.search(r'uid=(\d+)', cookie_str).group(1))

ACT = "HD2025031821201822"
PAGE = "YM2025040908558269"
TASK_COMP = "ZJ2025040709458367"
TASK_NODE = "FN1744160180RthG"

# 璺宠繃鐨勪换鍔＄被鍨?ID锛氱涓夋柟APP銆佷粯璐广€侀個璇枫€佸鐢熻璇併€佹闈㈢
SKIP_IDS = {266, 242, 183, 178, 39, 40, 8, 271, 272, 2, 33, 246}
# 娉細272/2/33/246 浠婂ぉ宸叉墜鍔ㄩ杩囷紝鍚庣画姣忓ぉ闇€瑕侀噸棰嗭紙姣忔棩閲嶇疆锛夛紝杩欓噷鍙啓姝讳粖澶╃殑

print("="*50)
print("銆?. 浠诲姟涓績绛惧埌銆?)
api = WPSAPI(cookie_str)
r = api.sign_in(user_id)
print("绛惧埌:", r.get('message','鎴愬姛') if r.get('success') else r.get('error'))

info = api.get_user_info(ACT, PAGE)
print(f"褰撳墠绉垎: {info.get('points')}  涔濆鏍煎墿浣? {info.get('lottery_times')}娆?)

print("\n銆?. 浠诲姟涓績鍋氫换鍔￠濂栥€?)
# 鍏堟媺浠诲姟鍒楄〃
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
    # 璺宠繃绫诲瀷锛氱涓夋柟APP銆佷粯璐广€侀個璇枫€佽璇併€佹闈㈢
    if event in ('exchange_traffic','trade','invite','auth','desktop_visit','desktop_install'):
        continue
    # 鍏?finish 鏍囪瀹屾垚锛屽啀 reward 棰嗗
    for action in ["task_center.finish", "task_center.reward"]:
        body = {"component_uniq_number":{"activity_number":ACT,"page_number":PAGE,
                "component_number":TASK_COMP,"component_node_id":TASK_NODE,"filter_params":{}},
                "component_type":35,"component_action":action,"task_center":{"task_id":tid}}
        resp = requests.post('https://personal-act.wps.cn/activity-rubik/activity/component_action',
                             headers=hdr, json=body, timeout=30)
        result = resp.json().get('result')
    done_tasks += 1
    print(f"  鉁?id={tid} {title} (finish+reward={result})")
print(f"鍏卞畬鎴?{done_tasks} 涓换鍔?)

# 閲嶆柊鏌ョН鍒嗗拰鎶藉
info = api.get_user_info(ACT, PAGE)
print(f"\n浠诲姟鍚庣Н鍒? {info.get('points')}  涔濆鏍煎墿浣? {info.get('lottery_times')}娆?)

print("\n銆?. 涔濆鏍兼娊濂栥€?)
for i in range(info.get('lottery_times',0)):
    r = api.lottery(ACT, PAGE, info.get('lottery_component_number',''), info.get('lottery_component_node_id',''))
    print(f"  绗瑊i+1}娆? {r.get('prize_name', r.get('error'))}")

print("\n銆?. 绂忓埄涓績锛堟墦鍗?璇曠敤/澶╁ぉ鎶藉锛夈€?)
tasks = DailyBenefitsTasks(load_accounts=False, enable_notification=False)
result = tasks.process_account({"account_name":"鑰佷竵","user_id":user_id,"cookies":cookie_str,"max_lottery_limit":10})
fb = result.get("free_member_checkin",{})
print(f"鎵撳崱: {fb.get('message','')}")
mt = result.get("member_trial",{})
print(f"璇曠敤: {mt.get('message','')}")
dl = result.get("daily_lottery",{})
for a in dl.get("attempts",[]):
    print(f"  澶╁ぉ鎶藉{a['index']}: {a.get('reward_name')}")

# 鏈€缁堢Н鍒?info = api.get_user_info(ACT, PAGE)
print(f"\n鏈€缁堢Н鍒? {info.get('points')}")
print("="*50)
print("鍏ㄩ儴瀹屾垚")
