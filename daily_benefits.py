#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
new Env('WPS澶╁ぉ棰嗙鍒?);
cron: 1 1 1 1 1
"""

"""
WPS 澶╁ぉ棰嗙鍒╂椿鍔ㄨ剼鏈?
褰撳墠鏀寔锛?- 鑷姩鍙戠幇鈥滅鍒╀腑蹇冣€濇椿鍔ㄥ叆鍙?- 鑷姩鑾峰彇椤甸潰娲诲姩淇℃伅
- 鑷姩鎵ц鎵撳崱鍏嶈垂棰嗕細鍛?- 鑷姩鍙備笌浼氬憳鍏嶈垂璇曠敤鐢宠
- 鑷姩鎵ц澶╁ぉ鎶藉

Author: Assistant
Date: 2026-03-11
"""

import json
import logging
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import requests

# 鑾峰彇椤圭洰鏍圭洰褰?project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from logging_utils import (
    bind_logger,
    configure_logging,
    get_logger,
    log_page_switch,
    log_task_result,
)
from notification import send_notification, NotificationSound


class DailyBenefitsAPI:
    """WPS 澶╁ぉ棰嗙鍒╂椿鍔ㄦ帴鍙ｅ皝瑁?""

    MARKET_ACTIVITY_URL = "https://tiance.wps.cn/dce/exec/api/market/activity"
    PAGE_INFO_URL = "https://personal-act.wps.cn/activity-rubik/activity/page_info"
    COMPONENT_ACTION_URL = "https://personal-act.wps.cn/activity-rubik/activity/component_action"

    # 渚濇鏌ヨ澶氫釜钀ラ攢娓犻亾骞跺悎骞跺叆鍙ｅ€欓€夛紝闈犲墠鐨勬笭閬撲紭鍏堢骇鏇撮珮銆?    # AUTOPCHYZXYYHD3737: PC 浼氬憳涓績杩愯惀娲诲姩鑱氬悎浣嶏紝鏃犻渶鐧诲綍鍗冲彲绋冲畾杩斿洖绂忓埄鍏ュ彛銆?    # HYGW5004,GWHD5002: 鏃ф笭閬擄紝浣滀负鍏滃簳锛堥儴鍒嗚处鍙风櫥褰曟€佷笅浠嶄細杩斿洖鍏ュ彛锛夈€?    MARKET_ACTIVITY_CHANNELS = [
        {
            "channel_code": "AUTOPCHYZXYYHD3737",
            "platform": 8,
            "version": "0.0.0.0"
        },
        {
            "channel_code": "HYGW5004,GWHD5002",
            "version": "",
            "platform": 8,
            "device": 1,
            "hdid": "",
            "filter_info": {}
        }
    ]

    # 鍏ュ彛鍒ゅ畾渚濇嵁娲诲姩閾炬帴 query 涓殑 position 鍙傛暟锛岀鍒╀腑蹇冨浐瀹氫负 pc_nvc_activity_fuli銆?    # 閫変腑浼樺厛绾э細position 绮剧‘鍛戒腑 > position 鍚?fuli > 鏍囬鍛戒腑銆?    TARGET_POSITIONS = ("pc_nvc_activity_fuli",)
    TARGET_TITLES = {"绂忓埄涓績", "澶╁ぉ棰嗙鍒?}

    def __init__(self, cookies: str, user_agent: Optional[str] = None):
        self.cookies = self._parse_cookies(cookies)
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
        )
        self.base_headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "application/json; charset=UTF-8",
            "sec-ch-ua-platform": '"macOS"',
            "sec-ch-ua": '"Not:A-Brand";v="99", "Brave";v="145", "Chromium";v="145"',
            "sec-ch-ua-mobile": "?0",
            "sec-gpc": "1",
            "accept-language": "zh-CN,zh;q=0.7",
            "origin": "https://personal-act.wps.cn",
            "referer": "https://personal-act.wps.cn/",
            "priority": "u=1, i"
        }
        configure_logging()
        self.logger = bind_logger(get_logger("daily_benefits.api"), page=DailyBenefitsTasks.page_name)

    @staticmethod
    def _parse_cookies(cookie_str: str) -> Dict[str, str]:
        """灏?Cookie 瀛楃涓茶В鏋愪负瀛楀吀"""
        cookies: Dict[str, str] = {}
        for item in cookie_str.split("; "):
            if "=" in item:
                key, value = item.split("=", 1)
                cookies[key] = value
        return cookies

    @staticmethod
    def _extract_error_message(result: Dict[str, Any]) -> str:
        """浠庤繑鍥炵粨鏋滀腑鎻愬彇閿欒娑堟伅"""
        return result.get("msg") or result.get("message") or result.get("error") or "鏈煡閿欒"

    @staticmethod
    def _normalize_server_time(server_time: Any) -> int:
        """鍏煎绉掑拰姣鏃堕棿鎴炽€?""
        try:
            timestamp = int(server_time)
        except (TypeError, ValueError):
            return 0

        if timestamp > 10 ** 12:
            timestamp //= 1000
        return timestamp

    @classmethod
    def _resolve_sign_date(cls, item: Dict[str, Any], sign_records: List[Dict[str, Any]]) -> str:
        """浼樺厛浣跨敤鏈嶅姟绔椂闂存帹瀵肩鍒版棩鏈燂紝缂哄け鏃跺洖閫€鍒拌褰曚腑鐨勬渶鏂版棩鏈熴€?""
        server_time = cls._normalize_server_time(item.get("server_time", 0))
        if server_time:
            return time.strftime("%Y-%m-%d", time.localtime(server_time))

        today = time.strftime("%Y-%m-%d")
        if any(record.get("sign_date") == today for record in sign_records):
            return today

        if sign_records:
            return sign_records[0].get("sign_date", today)

        return today

    @staticmethod
    def _count_signed_days(sign_records: List[Dict[str, Any]]) -> int:
        """缁熻褰撳墠绯诲垪宸茬鍒板ぉ鏁般€?""
        return sum(1 for record in sign_records if record.get("sign_status") == "signed")

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        """灏嗘帴鍙ｈ繑鍥炵殑鏁板瓧瀛楁瀹夊叏杞负 int銆?""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _is_auth_expired_message(message: str) -> bool:
        keywords = ("Token宸茶繃鏈?, "ErrNotLogin", "userNotLogin", "鏈櫥褰?, "璇烽噸鏂扮櫥褰?)
        return any(keyword in str(message) for keyword in keywords)

    def _build_failure_result(self, payload: Dict[str, Any], default_error: str = "鏈煡閿欒") -> Dict[str, Any]:
        error_message = self._extract_error_message(payload) or default_error
        result = {
            "success": False,
            "error": error_message
        }
        if (
            payload.get("code") == 2000000
            or payload.get("ext_msg") == "userNotLogin"
            or self._is_auth_expired_message(error_message)
        ):
            result["error_type"] = "token_expired"
        return result

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """缁熶竴璇锋眰鍏ュ彛"""
        request_headers = self.base_headers.copy()
        if headers:
            request_headers.update(headers)

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=request_headers,
                cookies=self.cookies,
                params=params,
                json=json_data,
                timeout=30
            )
            response.raise_for_status()
            return {
                "success": True,
                "data": response.json()
            }
        except requests.exceptions.RequestException as exc:
            return {
                "success": False,
                "error": f"缃戠粶璇锋眰澶辫触: {exc}"
            }
        except ValueError as exc:
            return {
                "success": False,
                "error": f"鍝嶅簲瑙ｆ瀽澶辫触: {exc}"
            }

    def get_market_activity(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """鑾峰彇鍗曚釜娓犻亾鐨勫競鍦烘椿鍔ㄦ暟鎹?""
        request_payload = payload if payload is not None else self.MARKET_ACTIVITY_CHANNELS[0]
        result = self._request(
            "POST",
            self.MARKET_ACTIVITY_URL,
            headers={
                "sec-fetch-site": "same-site",
                "sec-fetch-mode": "cors",
                "sec-fetch-dest": "empty"
            },
            json_data=request_payload
        )

        if not result["success"]:
            return result

        payload_data = result["data"]
        if payload_data.get("result") != "ok":
            return self._build_failure_result(payload_data)

        return {
            "success": True,
            "data": payload_data
        }

    def get_benefit_portal(self) -> Dict[str, Any]:
        """璺ㄥ涓惀閿€娓犻亾鍙戠幇骞堕€変腑銆屽ぉ澶╅绂忓埄銆嶆椿鍔ㄥ叆鍙?""
        raw_candidates: List[Dict[str, str]] = []
        channel_errors: List[str] = []
        auth_expired = False

        for channel_payload in self.MARKET_ACTIVITY_CHANNELS:
            channel_code = channel_payload.get("channel_code", "")
            market_result = self.get_market_activity(channel_payload)
            if not market_result["success"]:
                channel_errors.append(f"{channel_code}: {market_result.get('error', '鏈煡閿欒')}")
                if market_result.get("error_type") == "token_expired":
                    auth_expired = True
                continue
            self._collect_portal_candidates(market_result["data"], raw_candidates)

        parsed_candidates = self._parse_portal_candidates(raw_candidates)
        self.logger.info(
            "鍏ュ彛鍙戠幇锛氭敹闆嗗埌 %s 涓摼鎺ワ紝鍘婚噸鍚?%s 涓叆鍙?,
            len(raw_candidates),
            len(parsed_candidates),
            extra={"step": "鍏ュ彛鍙戠幇"}
        )

        if not parsed_candidates:
            failure = {"success": False, "error": "鏈壘鍒扮鍒╀腑蹇冩椿鍔ㄥ叆鍙?}
            if auth_expired:
                failure["error_type"] = "token_expired"
            elif channel_errors:
                failure["error"] = (
                    f"鏈壘鍒扮鍒╀腑蹇冩椿鍔ㄥ叆鍙ｏ紙娓犻亾璇锋眰澶辫触: {'; '.join(channel_errors)}锛?
                )
            return failure

        selected = self._select_benefit_portal(parsed_candidates)
        if selected is None:
            found_positions = sorted({
                candidate.get("position", "")
                for candidate in parsed_candidates
                if candidate.get("position")
            })
            return {
                "success": False,
                "error": (
                    "鏈尮閰嶅埌绂忓埄涓績鍏ュ彛锛堟湡鏈?position=pc_nvc_activity_fuli锛?
                    f"锛屽疄闄呭彂鐜? {', '.join(found_positions) or '鏃?position'}"
                )
            }
        return selected

    def _parse_portal_candidates(self, raw_candidates: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """瑙ｆ瀽鍊欓€夐摼鎺ュ苟鎸?activity/page 鍘婚噸锛岄檮甯?position/title銆?""
        parsed: List[Dict[str, Any]] = []
        seen: set = set()
        for candidate in raw_candidates:
            portal_info = self._parse_portal_link(candidate["link"])
            if not portal_info["success"]:
                continue

            dedup_key = (portal_info["activity_number"], portal_info["page_number"])
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            portal_info["title"] = candidate.get("title", "")
            portal_info["pic"] = candidate.get("pic", "")
            portal_info["position"] = portal_info.get("filter_params", {}).get("position", "")
            parsed.append(portal_info)
        return parsed

    def _select_benefit_portal(self, parsed_candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """鎸?position 绮剧‘鍛戒腑 > position 鍚?fuli > 鏍囬鍛戒腑 鐨勯『搴忛€変腑绂忓埄鍏ュ彛銆?""
        for candidate in parsed_candidates:
            if candidate.get("position") in self.TARGET_POSITIONS:
                return candidate

        for candidate in parsed_candidates:
            if "fuli" in (candidate.get("position") or ""):
                return candidate

        for candidate in parsed_candidates:
            if candidate.get("title") in self.TARGET_TITLES:
                return candidate

        return None

    def _collect_portal_candidates(self, node: Any, candidates: List[Dict[str, str]]) -> None:
        """閫掑綊鏀堕泦鍖呭惈 portal 閾炬帴鐨勬椿鍔ㄥ叆鍙ｏ紙涓嶅啀瑕佹眰鑺傜偣甯?title锛?""
        if isinstance(node, dict):
            link = node.get("link")
            if isinstance(link, str) and "/rubik2/portal/" in link:
                title = node.get("title")
                candidates.append({
                    "title": title if isinstance(title, str) else "",
                    "link": link,
                    "pic": node.get("pic") or node.get("img") or ""
                })

            for value in node.values():
                self._collect_portal_candidates(value, candidates)

        elif isinstance(node, list):
            for item in node:
                self._collect_portal_candidates(item, candidates)

    def _parse_portal_link(self, link: str) -> Dict[str, Any]:
        """瑙ｆ瀽娲诲姩 portal 閾炬帴"""
        try:
            parsed = urlparse(link)
            path_parts = [part for part in parsed.path.split("/") if part]
            portal_index = path_parts.index("portal")

            activity_number = path_parts[portal_index + 1]
            page_number = path_parts[portal_index + 2]

            query_params = parse_qs(parsed.query)
            filter_params = {
                key: values[0]
                for key, values in query_params.items()
                if values
            }

            return {
                "success": True,
                "link": link,
                "activity_number": activity_number,
                "page_number": page_number,
                "filter_params": filter_params
            }
        except (ValueError, IndexError) as exc:
            return {
                "success": False,
                "error": f"娲诲姩閾炬帴瑙ｆ瀽澶辫触: {exc}"
            }

    def get_page_info(self, portal_info: Dict[str, Any]) -> Dict[str, Any]:
        """鑾峰彇椤甸潰鍏ㄩ儴娲诲姩淇℃伅"""
        self.logger.info("鑾峰彇椤甸潰娲诲姩淇℃伅", extra={"step": "椤甸潰淇℃伅"})
        activity_number = portal_info["activity_number"]
        page_number = portal_info["page_number"]
        filter_params = portal_info.get("filter_params", {})

        result = self._request(
            "GET",
            self.PAGE_INFO_URL,
            headers={
                "sec-fetch-site": "same-origin",
                "sec-fetch-mode": "cors",
                "sec-fetch-dest": "empty",
                "referer": portal_info["link"]
            },
            params={
                "activity_number": activity_number,
                "page_number": page_number,
                "filter_params": json.dumps(filter_params, ensure_ascii=False, separators=(",", ":"))
            }
        )

        if not result["success"]:
            return result

        payload = result["data"]
        if payload.get("result") != "ok":
            return self._build_failure_result(payload)

        return {
            "success": True,
            "data": payload
        }

    def get_member_trial_info(self, page_info: Dict[str, Any]) -> Dict[str, Any]:
        """浠庢€绘椿鍔ㄨ繑鍥炴暟鎹腑鎻愬彇浼氬憳鍏嶈垂璇曠敤妯″潡"""
        data_list = page_info.get("data", [])
        fallback_item: Optional[Dict[str, Any]] = None

        for item in data_list:
            if not isinstance(item, dict):
                continue

            divide_prize = item.get("divide_prize")
            if not isinstance(divide_prize, dict):
                continue

            details = divide_prize.get("divide_prize_details") or []
            if not details:
                continue

            if fallback_item is None:
                fallback_item = item

            if any("浼氬憳" in str(detail.get("title", "")) for detail in details):
                return {
                    "success": True,
                    "component_number": item.get("number", ""),
                    "component_node_id": item.get("component_node_id", ""),
                    "remain_times": divide_prize.get("remain_times", 0),
                    "latest_result": divide_prize.get("latest_result", ""),
                    "join_reach_limit": divide_prize.get("join_reach_limit", False),
                    "details": details,
                    "raw_data": divide_prize
                }

        if fallback_item is not None:
            divide_prize = fallback_item.get("divide_prize", {})
            return {
                "success": True,
                "component_number": fallback_item.get("number", ""),
                "component_node_id": fallback_item.get("component_node_id", ""),
                "remain_times": divide_prize.get("remain_times", 0),
                "latest_result": divide_prize.get("latest_result", ""),
                "join_reach_limit": divide_prize.get("join_reach_limit", False),
                "details": divide_prize.get("divide_prize_details") or [],
                "raw_data": divide_prize
            }

        return {
            "success": False,
            "error": "鏈壘鍒颁細鍛樺厤璐硅瘯鐢ㄦā鍧?
        }

    def sign_up_member_trial(
        self,
        portal_info: Dict[str, Any],
        component_number: str,
        component_node_id: str,
        cycle_id: str,
        session_id: str
    ) -> Dict[str, Any]:
        """鎵ц浼氬憳鍏嶈垂璇曠敤鐢宠"""
        csrf_token = self.cookies.get("act_csrf_token") or self.cookies.get("csrf")
        if not csrf_token:
            return {
                "success": False,
                "error": "Cookie 涓己灏?act_csrf_token/csrf锛屾棤娉曟彁浜よ瘯鐢ㄧ敵璇?
            }

        payload = {
            "component_uniq_number": {
                "activity_number": portal_info["activity_number"],
                "page_number": portal_info["page_number"],
                "component_number": component_number,
                "component_node_id": component_node_id,
                "filter_params": {}
            },
            "component_type": 32,
            "component_action": "divide_prize.sign_up",
            "divide_prize": {
                "cycle_id": cycle_id,
                "session_id": session_id
            }
        }

        result = self._request(
            "POST",
            self.COMPONENT_ACTION_URL,
            headers={
                "Content-Type": "application/json",
                "x-act-csrf-token": csrf_token,
                "sec-fetch-site": "same-origin",
                "sec-fetch-mode": "cors",
                "sec-fetch-dest": "empty",
                "referer": (
                    f"https://personal-act.wps.cn/rubik2/portal/"
                    f"{portal_info['activity_number']}/{portal_info['page_number']}"
                )
            },
            json_data=payload
        )

        if not result["success"]:
            return result

        payload_data = result["data"]
        if payload_data.get("result") != "ok":
            return self._build_failure_result(payload_data)

        divide_prize = payload_data.get("data", {}).get("divide_prize", {})
        if divide_prize.get("success"):
            return {
                "success": True,
                "reason": divide_prize.get("reason", ""),
                "data": divide_prize
            }

        failure_result = {
            "success": False,
            "error": divide_prize.get("reason") or "璇曠敤鐢宠澶辫触",
            "data": divide_prize
        }
        if self._is_auth_expired_message(failure_result["error"]):
            failure_result["error_type"] = "token_expired"
        return failure_result

    def get_fragment_collect_info(self, page_info: Dict[str, Any]) -> Dict[str, Any]:
        """浠庢€绘椿鍔ㄨ繑鍥炴暟鎹腑鎻愬彇鎵撳崱鍏嶈垂棰嗕細鍛樻ā鍧?""
        data_list = page_info.get("data", [])
        fallback_item: Optional[Dict[str, Any]] = None

        for item in data_list:
            if not isinstance(item, dict):
                continue

            fragment_collect = item.get("fragment_collect")
            if not isinstance(fragment_collect, dict):
                continue

            sign_records = fragment_collect.get("sign_records") or []
            if not sign_records:
                continue

            if fallback_item is None:
                fallback_item = item

            sign_date = self._resolve_sign_date(item, sign_records)
            today_record = next(
                (record for record in sign_records if record.get("sign_date") == sign_date),
                None
            )
            sign_series_id = fragment_collect.get("sign_series_id", "")

            if item.get("type") == 42 or today_record is not None:
                return {
                    "success": True,
                    "component_number": item.get("number", ""),
                    "component_node_id": item.get("component_node_id", ""),
                    "sign_date": sign_date,
                    "sign_series_id": sign_series_id,
                    "is_new_sign_series": not bool(sign_series_id),
                    "is_signed": (today_record or {}).get("sign_status") == "signed",
                    "today_record": today_record or {},
                    "signed_days": self._count_signed_days(sign_records),
                    "sign_records": sign_records,
                    "raw_data": fragment_collect
                }

        if fallback_item is not None:
            fragment_collect = fallback_item.get("fragment_collect", {})
            sign_records = fragment_collect.get("sign_records") or []
            sign_date = self._resolve_sign_date(fallback_item, sign_records)
            today_record = next(
                (record for record in sign_records if record.get("sign_date") == sign_date),
                None
            )
            sign_series_id = fragment_collect.get("sign_series_id", "")
            return {
                "success": True,
                "component_number": fallback_item.get("number", ""),
                "component_node_id": fallback_item.get("component_node_id", ""),
                "sign_date": sign_date,
                "sign_series_id": sign_series_id,
                "is_new_sign_series": not bool(sign_series_id),
                "is_signed": (today_record or {}).get("sign_status") == "signed",
                "today_record": today_record or {},
                "signed_days": self._count_signed_days(sign_records),
                "sign_records": sign_records,
                "raw_data": fragment_collect
            }

        return {
            "success": False,
            "error": "鏈壘鍒版墦鍗″厤璐归浼氬憳妯″潡"
        }

    def sign_in_fragment_collect(
        self,
        portal_info: Dict[str, Any],
        component_number: str,
        component_node_id: str,
        sign_date: str,
        sign_series_id: str,
        is_new_sign_series: bool
    ) -> Dict[str, Any]:
        """鎵ц鎵撳崱鍏嶈垂棰嗕細鍛樼鍒?""
        csrf_token = self.cookies.get("act_csrf_token") or self.cookies.get("csrf")
        if not csrf_token:
            return {
                "success": False,
                "error": "Cookie 涓己灏?act_csrf_token/csrf锛屾棤娉曟墽琛屾墦鍗＄鍒?
            }

        payload = {
            "component_uniq_number": {
                "activity_number": portal_info["activity_number"],
                "page_number": portal_info["page_number"],
                "component_number": component_number,
                "component_node_id": component_node_id,
                "filter_params": portal_info.get("filter_params", {})
            },
            "component_type": 42,
            "component_action": "fragment_collect.sign_in",
            "fragment_collect": {
                "sign_date": sign_date,
                "series_id": sign_series_id,
                "is_new_sign_series": is_new_sign_series
            }
        }

        result = self._request(
            "POST",
            self.COMPONENT_ACTION_URL,
            headers={
                "Content-Type": "application/json",
                "x-act-csrf-token": csrf_token,
                "sec-fetch-site": "same-origin",
                "sec-fetch-mode": "cors",
                "sec-fetch-dest": "empty",
                "referer": portal_info["link"]
            },
            json_data=payload
        )

        if not result["success"]:
            return result

        payload_data = result["data"]
        if payload_data.get("result") != "ok":
            return self._build_failure_result(payload_data)

        fragment_collect = payload_data.get("data", {}).get("fragment_collect", {})
        if fragment_collect.get("success"):
            return {
                "success": True,
                "reason": fragment_collect.get("reason", ""),
                "data": fragment_collect
            }

        failure_result = {
            "success": False,
            "error": fragment_collect.get("reason") or "鎵撳崱绛惧埌澶辫触",
            "data": fragment_collect
        }
        if self._is_auth_expired_message(failure_result["error"]):
            failure_result["error_type"] = "token_expired"
        return failure_result

    @staticmethod
    def _pick_lottery_session(lottery_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """浼樺厛鎸戦€夎繘琛屼腑鐨勬娊濂栧満娆?""
        for session in lottery_list:
            if (
                session.get("session_status") == "IN_PROGRESS"
                and session.get("stock_status") in {"IN_STOCK", "", None}
            ):
                return session

        for session in lottery_list:
            if session.get("session_status") == "IN_PROGRESS":
                return session

        return lottery_list[0] if lottery_list else None

    def get_daily_lottery_info(self, page_info: Dict[str, Any]) -> Dict[str, Any]:
        """浠庢€绘椿鍔ㄨ繑鍥炴暟鎹腑鎻愬彇澶╁ぉ鎶藉妯″潡"""
        data_list = page_info.get("data", [])
        fallback_item: Optional[Dict[str, Any]] = None
        fallback_session: Optional[Dict[str, Any]] = None

        for item in data_list:
            if not isinstance(item, dict):
                continue

            lottery_v2 = item.get("lottery_v2")
            if not isinstance(lottery_v2, dict):
                continue

            lottery_list = lottery_v2.get("lottery_list") or []
            if not lottery_list:
                continue

            selected_session = self._pick_lottery_session(lottery_list)
            if selected_session is None:
                continue

            if fallback_item is None:
                fallback_item = item
                fallback_session = selected_session

            if selected_session.get("session_status") == "IN_PROGRESS":
                sign_day = self._safe_int(selected_session.get("times", 0))
                return {
                    "success": True,
                    "component_number": item.get("number", ""),
                    "component_node_id": item.get("component_node_id", ""),
                    "session_id": selected_session.get("session_id"),
                    "session_name": selected_session.get("session_name", ""),
                    "remain_times": sign_day,
                    "sign_day": sign_day,
                    "stock_status": selected_session.get("stock_status", ""),
                    "share_times": lottery_v2.get("share_times", False),
                    "share_times_count": lottery_v2.get("share_times_count", 0),
                    "lottery_reward_list": selected_session.get("lottery_reward_list", []),
                    "raw_data": lottery_v2
                }

        if fallback_item is not None and fallback_session is not None:
            lottery_v2 = fallback_item.get("lottery_v2", {})
            sign_day = self._safe_int(fallback_session.get("times", 0))
            return {
                "success": True,
                "component_number": fallback_item.get("number", ""),
                "component_node_id": fallback_item.get("component_node_id", ""),
                "session_id": fallback_session.get("session_id"),
                "session_name": fallback_session.get("session_name", ""),
                "remain_times": 0,
                "sign_day": sign_day,
                "stock_status": fallback_session.get("stock_status", ""),
                "share_times": lottery_v2.get("share_times", False),
                "share_times_count": lottery_v2.get("share_times_count", 0),
                "lottery_reward_list": fallback_session.get("lottery_reward_list", []),
                "raw_data": lottery_v2
            }

        return {
            "success": False,
            "error": "鏈壘鍒板ぉ澶╂娊濂栨ā鍧?
        }

    def exec_daily_lottery(
        self,
        portal_info: Dict[str, Any],
        component_number: str,
        component_node_id: str,
        session_id: Any
    ) -> Dict[str, Any]:
        """鎵ц澶╁ぉ鎶藉"""
        csrf_token = self.cookies.get("act_csrf_token") or self.cookies.get("csrf")
        if not csrf_token:
            return {
                "success": False,
                "error": "Cookie 涓己灏?act_csrf_token/csrf锛屾棤娉曟墽琛屾娊濂?
            }

        payload = {
            "component_uniq_number": {
                "activity_number": portal_info["activity_number"],
                "page_number": portal_info["page_number"],
                "component_number": component_number,
                "component_node_id": component_node_id,
                "filter_params": portal_info.get("filter_params", {})
            },
            "component_type": 45,
            "component_action": "lottery_v2.exec",
            "lottery_v2": {
                "session_id": session_id
            }
        }

        result = self._request(
            "POST",
            self.COMPONENT_ACTION_URL,
            headers={
                "Content-Type": "application/json",
                "x-act-csrf-token": csrf_token,
                "sec-fetch-site": "same-origin",
                "sec-fetch-mode": "cors",
                "sec-fetch-dest": "empty",
                "referer": portal_info["link"]
            },
            json_data=payload
        )

        if not result["success"]:
            return result

        payload_data = result["data"]
        if payload_data.get("result") != "ok":
            return self._build_failure_result(payload_data)

        lottery_v2 = payload_data.get("data", {}).get("lottery_v2", {})
        if lottery_v2.get("success"):
            return {
                "success": True,
                "reward_name": lottery_v2.get("reward_name", "鏈煡濂栧搧"),
                "reward_type": lottery_v2.get("reward_type", ""),
                "reward_id": lottery_v2.get("reward_id", 0),
                "order_id": lottery_v2.get("order_id", ""),
                "img": lottery_v2.get("img", ""),
                "data": lottery_v2
            }

        failure_result = {
            "success": False,
            "error": lottery_v2.get("send_msg") or "鎶藉澶辫触",
            "error_code": lottery_v2.get("error_code", 0),
            "data": lottery_v2
        }
        if self._is_auth_expired_message(failure_result["error"]):
            failure_result["error_type"] = "token_expired"
        return failure_result

    def receive_daily_lottery_reward(
        self,
        portal_info: Dict[str, Any],
        component_number: str,
        component_node_id: str,
        sign_series_id: str
    ) -> Dict[str, Any]:
        """棰嗗彇澶╁ぉ绂忓埄绗?7 澶╁鍔?""
        csrf_token = self.cookies.get("act_csrf_token") or self.cookies.get("csrf")
        if not csrf_token:
            return {
                "success": False,
                "error": "Cookie 涓己灏?act_csrf_token/csrf锛屾棤娉曢鍙栫7澶╁鍔?
            }

        payload = {
            "component_uniq_number": {
                "activity_number": portal_info["activity_number"],
                "page_number": portal_info["page_number"],
                "component_number": component_number,
                "component_node_id": component_node_id,
                "filter_params": portal_info.get("filter_params", {})
            },
            "component_type": 42,
            "component_action": "fragment_collect.receive",
            "fragment_collect": {
                "series_id": sign_series_id
            }
        }

        result = self._request(
            "POST",
            self.COMPONENT_ACTION_URL,
            headers={
                "Content-Type": "application/json",
                "x-act-csrf-token": csrf_token,
                "sec-fetch-site": "same-origin",
                "sec-fetch-mode": "cors",
                "sec-fetch-dest": "empty",
                "referer": portal_info["link"]
            },
            json_data=payload
        )

        if not result["success"]:
            return result

        payload_data = result["data"]
        if payload_data.get("result") != "ok":
            return self._build_failure_result(payload_data)

        action_data = payload_data.get("data", {}).get("fragment_collect", {})
        if not action_data:
            action_data = payload_data.get("data", {}).get("lottery_v2", {})

        if action_data.get("success"):
            return {
                "success": True,
                "reason": action_data.get("reason", ""),
                "reward_name": action_data.get("reward_name", ""),
                "data": action_data
            }

        error_message = (
            action_data.get("reason")
            or action_data.get("send_msg")
            or action_data.get("message")
            or "棰嗗彇绗?澶╁鍔卞け璐?
        )
        failure_result = {
            "success": False,
            "error": error_message,
            "data": action_data,
            "payload_summary": {
                "component_type": payload["component_type"],
                "component_action": payload["component_action"],
                "component_number": component_number,
                "component_node_id": component_node_id,
                "sign_series_id": sign_series_id
            }
        }
        if self._is_auth_expired_message(failure_result["error"]):
            failure_result["error_type"] = "token_expired"
        return failure_result


class DailyBenefitsTasks:
    """澶╁ぉ棰嗙鍒╂椿鍔ㄤ换鍔℃墽琛屽櫒"""

    page_name = "澶╁ぉ棰嗙鍒?

    def __init__(self, config_path: str = None, enable_notification: bool = True, load_accounts: bool = True):
        if config_path is None:
            self.config_path = project_root / "config" / "token.json"
        else:
            self.config_path = Path(config_path)

        self.enable_notification = enable_notification
        self.logger = self._setup_logger()
        self.accounts: List[Dict[str, Any]] = []
        self.account_results: List[Dict[str, Any]] = []
        if load_accounts:
            self._init_accounts()

    def _setup_logger(self) -> logging.Logger:
        configure_logging()
        return bind_logger(get_logger("daily_benefits"), page=self.page_name)

    @staticmethod
    def _is_auth_expired_message(message: str) -> bool:
        keywords = ("Token宸茶繃鏈?, "ErrNotLogin", "userNotLogin", "鏈櫥褰?, "璇烽噸鏂扮櫥褰?)
        return any(keyword in str(message) for keyword in keywords)

    @staticmethod
    def _is_broken_series_error(message: str) -> bool:
        """鍒ゆ柇鎵撳崱澶辫触鏄惁鍥犳棫 series 鏂/杩囨湡锛堥渶瑕侀噸鏂板紑鍚鍒帮級銆?""
        text = str(message).lower()
        return "not in series" in text or "series records" in text

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        """灏嗘帴鍙ｈ繑鍥炵殑鏁板瓧瀛楁瀹夊叏杞负 int銆?""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _init_accounts(self) -> None:
        """璇诲彇 WPS 璐﹀彿閰嶇疆"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"閰嶇疆鏂囦欢涓嶅瓨鍦? {self.config_path}")

        try:
            with open(self.config_path, "r", encoding="utf-8") as file:
                config_data = json.load(file)
        except json.JSONDecodeError as exc:
            raise ValueError(f"閰嶇疆鏂囦欢 JSON 瑙ｆ瀽澶辫触: {exc}") from exc

        wps_config = config_data.get("wps", {})
        self.accounts = wps_config.get("accounts", [])

        if self.accounts:
            self.logger.info(f"鎴愬姛鍔犺浇 {len(self.accounts)} 涓?WPS 璐﹀彿")
        else:
            self.logger.warning("閰嶇疆鏂囦欢涓病鏈夋壘鍒?WPS 璐﹀彿淇℃伅")

    @staticmethod
    def _sync_free_member_checkin_state(
        free_member_checkin: Dict[str, Any],
        fragment_result: Dict[str, Any]
    ) -> None:
        """灏嗛〉闈㈡渶鏂扮鍒扮姸鎬佸洖濉埌姹囨€荤粨鏋溿€?""
        today_record = fragment_result.get("today_record", {})
        free_member_checkin["sign_date"] = fragment_result.get("sign_date", "")
        free_member_checkin["sign_status"] = today_record.get("sign_status", "")
        free_member_checkin["reward_title"] = today_record.get("reward_title", "")
        free_member_checkin["signed_days"] = fragment_result.get("signed_days", 0)
        free_member_checkin["sign_series_id"] = fragment_result.get("sign_series_id", "")

    @staticmethod
    def _build_free_member_checkin_message(
        free_member_checkin: Dict[str, Any],
        *,
        signed_now: bool = False
    ) -> str:
        """缁熶竴鐢熸垚鎵撳崱鍏嶈垂棰嗕細鍛樻ā鍧楁枃妗堛€?""
        sign_date = free_member_checkin.get("sign_date", "")
        signed_days = free_member_checkin.get("signed_days", 0)
        reward_title = free_member_checkin.get("reward_title", "")
        sign_status = free_member_checkin.get("sign_status", "")

        if sign_status == "signed":
            day_text = f"杩炵画绗?{signed_days} 澶? if signed_days else sign_date
            reward_text = f"锛屽鍔? {reward_title}" if reward_title else ""
            if signed_now:
                return f"鎵撳崱鍏嶈垂棰嗕細鍛樼鍒版垚鍔燂紝{day_text}锛坽sign_date}锛墈reward_text}"
            return f"鎵撳崱鍏嶈垂棰嗕細鍛樹粖鏃ュ凡绛惧埌锛寋day_text}锛坽sign_date}锛墈reward_text}"

        return f"鎵撳崱鍏嶈垂棰嗕細鍛樺緟绛惧埌锛坽sign_date}锛?

    @staticmethod
    def _summarize_lottery_item(index: int, item: Dict[str, Any]) -> Dict[str, Any]:
        """鎻愬彇 lottery_v2 涓敤浜庢帓鏌ョ鍒?棰嗗彇椤哄簭鐨勫畨鍏ㄥ瓧娈点€?""
        lottery_v2 = item.get("lottery_v2") or {}
        lottery_list = lottery_v2.get("lottery_list") or []
        return {
            "index": index,
            "type": item.get("type"),
            "number": item.get("number", ""),
            "component_node_id": item.get("component_node_id", ""),
            "sessions": [
                {
                    "session_id": session.get("session_id", ""),
                    "session_name": session.get("session_name", ""),
                    "session_status": session.get("session_status", ""),
                    "stock_status": session.get("stock_status", ""),
                    "times": session.get("times", 0),
                    "reward_names": [
                        reward.get("reward_name", "")
                        for reward in session.get("lottery_reward_list", [])
                        if reward.get("reward_name")
                    ]
                }
                for session in lottery_list
                if isinstance(session, dict)
            ],
            "share_times": lottery_v2.get("share_times", False),
            "share_times_count": lottery_v2.get("share_times_count", 0)
        }

    @staticmethod
    def _summarize_fragment_item(index: int, item: Dict[str, Any]) -> Dict[str, Any]:
        """鎻愬彇 fragment_collect 涓敤浜庢帓鏌ョ鍒?棰嗗彇椤哄簭鐨勫畨鍏ㄥ瓧娈点€?""
        fragment_collect = item.get("fragment_collect") or {}
        sign_records = fragment_collect.get("sign_records") or []
        return {
            "index": index,
            "type": item.get("type"),
            "number": item.get("number", ""),
            "component_node_id": item.get("component_node_id", ""),
            "sign_series_id": fragment_collect.get("sign_series_id", ""),
            "signed_days_from_records": DailyBenefitsAPI._count_signed_days(sign_records),
            "sign_records": [
                {
                    "sign_date": record.get("sign_date", ""),
                    "sign_status": record.get("sign_status", ""),
                    "reward_title": record.get("reward_title", "")
                }
                for record in sign_records
                if isinstance(record, dict)
            ]
        }

    @classmethod
    def _build_page_diagnostics(
        cls,
        page_info: Dict[str, Any],
        fragment_result: Optional[Dict[str, Any]] = None,
        lottery_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """鐢熸垚涓嶅惈 Cookie/Token 鐨勯〉闈㈢姸鎬佽瘖鏂憳瑕併€?""
        data_list = page_info.get("data", [])
        if not isinstance(data_list, list):
            data_list = []

        lottery_items = [
            cls._summarize_lottery_item(index, item)
            for index, item in enumerate(data_list)
            if isinstance(item, dict) and isinstance(item.get("lottery_v2"), dict)
        ]
        fragment_items = [
            cls._summarize_fragment_item(index, item)
            for index, item in enumerate(data_list)
            if isinstance(item, dict) and isinstance(item.get("fragment_collect"), dict)
        ]
        item_43 = data_list[43] if len(data_list) > 43 and isinstance(data_list[43], dict) else {}

        diagnostics = {
            "data_count": len(data_list),
            "item_43": {
                "keys": list(item_43.keys()) if item_43 else [],
                "lottery_v2": cls._summarize_lottery_item(43, item_43) if item_43.get("lottery_v2") else {},
                "fragment_collect": cls._summarize_fragment_item(43, item_43) if item_43.get("fragment_collect") else {}
            },
            "fragment_result": {
                key: fragment_result.get(key)
                for key in [
                    "success",
                    "sign_date",
                    "sign_series_id",
                    "is_new_sign_series",
                    "is_signed",
                    "signed_days"
                ]
            } if fragment_result else {},
            "lottery_result": {
                key: lottery_result.get(key)
                for key in [
                    "success",
                    "session_id",
                    "session_name",
                    "remain_times",
                    "sign_day",
                    "stock_status"
                ]
            } if lottery_result else {},
            "fragment_items": fragment_items,
            "lottery_items": lottery_items
        }
        return diagnostics

    @staticmethod
    def _format_diagnostics(diagnostics: Dict[str, Any]) -> str:
        """鏍煎紡鍖栬瘖鏂憳瑕侊紝淇濇寔鏃ュ織鍗曡杈撳嚭銆?""
        return json.dumps(diagnostics, ensure_ascii=False, default=str, separators=(",", ":"))

    def _process_member_trial(
        self,
        api: DailyBenefitsAPI,
        portal_result: Dict[str, Any],
        page_info: Dict[str, Any],
        account_name: str,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """澶勭悊浼氬憳鍏嶈垂璇曠敤妯″潡"""
        trial_logger = bind_logger(self.logger, account=account_name, step="浼氬憳璇曠敤")
        member_trial_result = api.get_member_trial_info(page_info)
        if not member_trial_result["success"]:
            message = member_trial_result["error"]
            result["member_trial"]["message"] = message
            return {
                "success": False,
                "message": message
            }

        details = member_trial_result["details"]
        remain_times = member_trial_result["remain_times"]
        join_reach_limit = member_trial_result["join_reach_limit"]
        candidates = [detail for detail in details if not detail.get("has_join")]

        result["member_trial"]["remain_times"] = remain_times
        result["member_trial"]["candidates"] = [
            {
                "title": detail.get("title", ""),
                "session_id": detail.get("session_id", ""),
                "cycle_id": detail.get("cycle_id", ""),
                "has_join": detail.get("has_join", False),
                "stock": detail.get("stock", 0)
            }
            for detail in details
        ]

        if join_reach_limit:
            message = "浼氬憳鍏嶈垂璇曠敤浠婃棩鐢宠娆℃暟宸茶揪涓婇檺"
            result["member_trial"]["message"] = message
            return {
                "success": True,
                "message": message
            }

        if remain_times <= 0:
            message = "浼氬憳鍏嶈垂璇曠敤鏃犲墿浣欑敵璇锋鏁?
            result["member_trial"]["message"] = message
            return {
                "success": True,
                "message": message
            }

        if not candidates:
            message = "浼氬憳鍏嶈垂璇曠敤宸插叏閮ㄧ敵璇凤紝鏃犻渶閲嶅鎻愪氦"
            result["member_trial"]["message"] = message
            return {
                "success": True,
                "message": message
            }

        selected_candidates = candidates[:remain_times]
        trial_logger.info(
            "鍓╀綑鐢宠娆℃暟=%s锛屾湰娆″噯澶囩敵璇?%s 椤?,
            remain_times,
            len(selected_candidates)
        )

        for index, candidate in enumerate(selected_candidates, start=1):
            if index > 1:
                delay = random.uniform(1, 2)
                trial_logger.info("绛夊緟 %.1f 绉掑悗缁х画鐢宠", delay)
                time.sleep(delay)

            trial_logger.info(
                "姝ｅ湪鐢宠绗?%s 椤? %s",
                index,
                candidate.get("title", "鏈煡璇曠敤")
            )
            sign_up_result = api.sign_up_member_trial(
                portal_info=portal_result,
                component_number=member_trial_result["component_number"],
                component_node_id=member_trial_result["component_node_id"],
                cycle_id=candidate["cycle_id"],
                session_id=candidate["session_id"]
            )

            attempt = {
                "title": candidate.get("title", ""),
                "session_id": candidate.get("session_id", ""),
                "cycle_id": candidate.get("cycle_id", ""),
                "success": sign_up_result["success"],
                "message": sign_up_result.get("reason") or sign_up_result.get("error") or "鐢宠鎴愬姛"
            }
            result["member_trial"]["attempts"].append(attempt)

            if sign_up_result["success"]:
                trial_logger.info("%s 鐢宠鎴愬姛", attempt["title"])
            else:
                trial_logger.error("%s 鐢宠澶辫触: %s", attempt["title"], attempt["message"])
                if (
                    sign_up_result.get("error_type") == "token_expired"
                    or self._is_auth_expired_message(attempt["message"])
                ):
                    result["auth_expired"] = True
                    result["member_trial"]["message"] = "Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?
                    return {
                        "success": False,
                        "message": "Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?
                    }

        success_count = sum(1 for attempt in result["member_trial"]["attempts"] if attempt["success"])
        total_attempts = len(result["member_trial"]["attempts"])

        if total_attempts == 0:
            message = "鏈墽琛屼細鍛樺厤璐硅瘯鐢ㄧ敵璇?
            success = True
        elif success_count == total_attempts:
            message = f"浼氬憳鍏嶈垂璇曠敤鐢宠瀹屾垚锛屾垚鍔?{success_count} 椤?
            success = True
        elif success_count > 0:
            message = f"浼氬憳鍏嶈垂璇曠敤鐢宠閮ㄥ垎鎴愬姛锛屾垚鍔?{success_count}/{total_attempts} 椤?
            success = True
        else:
            message = f"浼氬憳鍏嶈垂璇曠敤鐢宠澶辫触锛屽叡灏濊瘯 {total_attempts} 椤?
            success = False

        result["member_trial"]["message"] = message
        return {
            "success": success,
            "message": message
        }

    def _process_fragment_collect_sign_in(
        self,
        api: DailyBenefitsAPI,
        portal_result: Dict[str, Any],
        page_info: Dict[str, Any],
        account_name: str,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """澶勭悊鎵撳崱鍏嶈垂棰嗕細鍛樻ā鍧?""
        checkin_logger = bind_logger(self.logger, account=account_name, step="鎵撳崱绛惧埌")
        fragment_result = api.get_fragment_collect_info(page_info)
        if not fragment_result["success"]:
            message = fragment_result["error"]
            result["free_member_checkin"]["message"] = message
            return {
                "success": False,
                "message": message,
                "refresh_page_info": False
            }

        self._sync_free_member_checkin_state(result["free_member_checkin"], fragment_result)

        if fragment_result["is_signed"]:
            message = self._build_free_member_checkin_message(result["free_member_checkin"])
            result["free_member_checkin"]["message"] = message
            return {
                "success": True,
                "message": message,
                "refresh_page_info": False,
                "signed_now": False
            }

        checkin_logger.info(
            "寮€濮嬫墽琛屾墦鍗＄鍒帮紝鏃ユ湡=%s, series_id=%s, is_new=%s",
            fragment_result["sign_date"],
            fragment_result.get("sign_series_id", ""),
            fragment_result.get("is_new_sign_series", True)
        )
        sign_in_result = api.sign_in_fragment_collect(
            portal_info=portal_result,
            component_number=fragment_result["component_number"],
            component_node_id=fragment_result["component_node_id"],
            sign_date=fragment_result["sign_date"],
            sign_series_id=fragment_result.get("sign_series_id", ""),
            is_new_sign_series=fragment_result.get("is_new_sign_series", True)
        )

        # 鏃?series 鏂/杩囨湡锛堟湇鍔＄杩斿洖 "not in series records"锛夋椂锛岃嚜鍔ㄤ互
        # 鈥滈噸鏂板紑鍚鍒扳€濈殑鍙傛暟閲嶈瘯涓€娆★細sign_date 鐣欑┖ + is_new_sign_series=true锛?        # 鏈嶅姟绔細寮€鍚竴鏉℃柊 series 骞舵妸浠婂ぉ绛句负绗?1 澶╋紙绛変环浜庨〉闈㈡墜鍔ㄧ偣鈥滈噸鏂板紑濮嬧€濓級銆?        if (
            not sign_in_result["success"]
            and self._is_broken_series_error(sign_in_result.get("error", ""))
        ):
            checkin_logger.info(
                "妫€娴嬪埌鏃?series 宸茶繃鏈燂紙%s锛夛紝鑷姩閲嶆柊寮€鍚鍒?,
                sign_in_result.get("error", "")
            )
            result["free_member_checkin"]["restarted_series"] = True
            sign_in_result = api.sign_in_fragment_collect(
                portal_info=portal_result,
                component_number=fragment_result["component_number"],
                component_node_id=fragment_result["component_node_id"],
                sign_date="",
                sign_series_id=fragment_result.get("sign_series_id", ""),
                is_new_sign_series=True
            )

        if sign_in_result["success"]:
            message = "鎵撳崱鍏嶈垂棰嗕細鍛樼鍒版垚鍔燂紝姝ｅ湪鍒锋柊绛惧埌鐘舵€?
            result["free_member_checkin"]["message"] = message
            return {
                "success": True,
                "message": message,
                "refresh_page_info": True,
                "signed_now": True
            }

        message = sign_in_result.get("error", "鎵撳崱绛惧埌澶辫触")
        if (
            sign_in_result.get("error_type") == "token_expired"
            or self._is_auth_expired_message(message)
        ):
            result["auth_expired"] = True
            message = "Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?
        checkin_logger.info(
            "鎵撳崱澶辫触鍝嶅簲璇婃柇: %s",
            self._format_diagnostics({
                "message": message,
                "response_data": sign_in_result.get("data", {}),
                "page_state": self._build_page_diagnostics(page_info, fragment_result=fragment_result)
            })
        )
        result["free_member_checkin"]["message"] = message
        return {
            "success": False,
            "message": message,
            "refresh_page_info": False
        }

    def _process_daily_lottery(
        self,
        api: DailyBenefitsAPI,
        portal_result: Dict[str, Any],
        page_info: Dict[str, Any],
        account_name: str,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """澶勭悊澶╁ぉ鎶藉妯″潡"""
        lottery_logger = bind_logger(self.logger, account=account_name, step="澶╁ぉ鎶藉")
        daily_lottery_result = api.get_daily_lottery_info(page_info)
        if not daily_lottery_result["success"]:
            message = daily_lottery_result["error"]
            result["daily_lottery"]["message"] = message
            return {
                "success": False,
                "message": message
            }

        remain_times = daily_lottery_result["remain_times"]
        session_id = daily_lottery_result["session_id"]
        result["daily_lottery"]["remain_times"] = remain_times
        result["daily_lottery"]["session_id"] = session_id
        result["daily_lottery"]["session_name"] = daily_lottery_result.get("session_name", "")
        result["daily_lottery"]["stock_status"] = daily_lottery_result.get("stock_status", "")
        result["daily_lottery"]["sign_day"] = daily_lottery_result.get("sign_day", 0)
        result["daily_lottery"]["reward_pool"] = [
            reward.get("reward_name", "")
            for reward in daily_lottery_result.get("lottery_reward_list", [])
            if reward.get("reward_name")
        ]

        if remain_times <= 0:
            message = "澶╁ぉ鎶藉鏃犲墿浣欐鏁?
            result["daily_lottery"]["message"] = message
            return {
                "success": True,
                "message": message
            }

        lottery_logger.info(
            "鍓╀綑鎶藉娆℃暟=%s锛屽紑濮嬫墽琛屾娊濂?,
            remain_times
        )

        for index in range(1, remain_times + 1):
            if index > 1:
                delay = random.uniform(1, 2)
                lottery_logger.info("绛夊緟 %.1f 绉掑悗缁х画鎶藉", delay)
                time.sleep(delay)

            lottery_exec_result = api.exec_daily_lottery(
                portal_info=portal_result,
                component_number=daily_lottery_result["component_number"],
                component_node_id=daily_lottery_result["component_node_id"],
                session_id=session_id
            )

            attempt = {
                "index": index,
                "success": lottery_exec_result["success"],
                "reward_name": lottery_exec_result.get("reward_name", ""),
                "reward_type": lottery_exec_result.get("reward_type", ""),
                "message": lottery_exec_result.get("error") or lottery_exec_result.get("reward_name") or "鎶藉鎴愬姛"
            }
            result["daily_lottery"]["attempts"].append(attempt)

            if lottery_exec_result["success"]:
                lottery_logger.info("绗?%s 娆℃娊濂栨垚鍔? %s", index, attempt["reward_name"])
            else:
                lottery_logger.error("绗?%s 娆℃娊濂栧け璐? %s", index, attempt["message"])
                if (
                    lottery_exec_result.get("error_type") == "token_expired"
                    or self._is_auth_expired_message(attempt["message"])
                ):
                    result["auth_expired"] = True
                    result["daily_lottery"]["message"] = "Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?
                    return {
                        "success": False,
                        "message": "Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?
                    }
                break

        success_count = sum(1 for attempt in result["daily_lottery"]["attempts"] if attempt["success"])
        total_attempts = len(result["daily_lottery"]["attempts"])

        if total_attempts == 0:
            message = "鏈墽琛屽ぉ澶╂娊濂?
            success = True
        elif success_count == total_attempts:
            message = f"澶╁ぉ鎶藉瀹屾垚锛屾垚鍔?{success_count} 娆?
            success = True
        elif success_count > 0:
            message = f"澶╁ぉ鎶藉閮ㄥ垎鎴愬姛锛屾垚鍔?{success_count}/{total_attempts} 娆?
            success = True
        else:
            message = f"澶╁ぉ鎶藉澶辫触锛屽叡灏濊瘯 {total_attempts} 娆?
            success = False

        if success_count > 0:
            reward_claim_status = self._process_daily_lottery_reward_claim(
                api=api,
                portal_result=portal_result,
                account_name=account_name,
                result=result
            )
            if reward_claim_status["message"]:
                message = f"{message}锛寋reward_claim_status['message']}"
            success = success and reward_claim_status["success"]

        result["daily_lottery"]["message"] = message
        return {
            "success": success,
            "message": message
        }

    def _claim_daily_lottery_reward_if_ready(
        self,
        api: DailyBenefitsAPI,
        portal_result: Dict[str, Any],
        page_info: Dict[str, Any],
        account_name: str,
        result: Dict[str, Any],
        *,
        force_claim: bool = False,
        fragment_result: Optional[Dict[str, Any]] = None,
        include_skip_message: bool = False
    ) -> Dict[str, Any]:
        """褰撳墠椤甸潰宸叉弧瓒崇 7 澶╂潯浠舵椂棰嗗彇濂栧姳銆?""
        claim_logger = bind_logger(self.logger, account=account_name, step="绗?澶╁鍔?)
        reward_claim = result["daily_lottery"].setdefault(
            "reward_claim",
            {
                "attempted": False,
                "success": False,
                "message": ""
            }
        )

        lottery_result = api.get_daily_lottery_info(page_info)
        if not lottery_result["success"]:
            message = f"绗?澶╁鍔辩姸鎬佽В鏋愬け璐? {lottery_result['error']}"
            reward_claim["message"] = message
            return {
                "success": False,
                "message": message,
                "claimed": False
            }

        if fragment_result is None:
            fragment_result = api.get_fragment_collect_info(page_info)
        if not fragment_result["success"]:
            message = f"绗?澶╁鍔辩鍒扮姸鎬佽В鏋愬け璐? {fragment_result['error']}"
            reward_claim["message"] = message
            return {
                "success": False,
                "message": message,
                "claimed": False
            }

        result["daily_lottery"]["sign_day"] = lottery_result.get("sign_day", 0)
        sign_day = lottery_result.get("sign_day", 0)
        if not force_claim and sign_day != 7:
            message = ""
            if include_skip_message and sign_day > 0:
                message = f"褰撳墠绛惧埌绗?{sign_day} 澶╋紝鏈埌绗?7 澶╅鍙栨潯浠?
            return {
                "success": True,
                "message": message,
                "claimed": False
            }

        reward_claim["attempted"] = True
        claim_logger.info("褰撳墠绛惧埌绗?7 澶╋紝寮€濮嬮鍙栧鍔?)
        receive_result = api.receive_daily_lottery_reward(
            portal_info=portal_result,
            component_number=fragment_result["component_number"],
            component_node_id=fragment_result["component_node_id"],
            sign_series_id=fragment_result.get("sign_series_id", "")
        )

        if receive_result["success"]:
            reward_name = receive_result.get("reward_name", "")
            message = receive_result.get("reason")
            if not message:
                message = f"绗?澶╁鍔遍鍙栨垚鍔? {reward_name}" if reward_name else "绗?澶╁鍔遍鍙栨垚鍔?
            reward_claim["success"] = True
            reward_claim["message"] = message
            return {
                "success": True,
                "message": message,
                "claimed": True
            }

        message = receive_result.get("error", "绗?澶╁鍔遍鍙栧け璐?)
        if (
            receive_result.get("error_type") == "token_expired"
            or self._is_auth_expired_message(message)
        ):
            result["auth_expired"] = True
            message = "Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?
        claim_logger.info(
            "绗?澶╁鍔遍鍙栧け璐ヨ瘖鏂? %s",
            self._format_diagnostics({
                "message": message,
                "response_data": receive_result.get("data", {}),
                "payload_summary": receive_result.get("payload_summary", {})
            })
        )

        reward_claim["success"] = False
        reward_claim["message"] = message
        return {
            "success": False,
            "message": message,
            "claimed": False
        }

    def _process_daily_lottery_reward_claim(
        self,
        api: DailyBenefitsAPI,
        portal_result: Dict[str, Any],
        account_name: str,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """鍒锋柊绛惧埌澶╂暟锛屽苟鍦ㄧ 7 澶╅鍙栧鍔便€?""
        claim_logger = bind_logger(self.logger, account=account_name, step="绗?澶╁鍔?)
        reward_claim = result["daily_lottery"].setdefault(
            "reward_claim",
            {
                "attempted": False,
                "success": False,
                "message": ""
            }
        )

        refreshed_page_info_result = api.get_page_info(portal_result)
        if not refreshed_page_info_result["success"]:
            message = f"鍒锋柊绛惧埌澶╂暟澶辫触: {refreshed_page_info_result['error']}"
            reward_claim["message"] = message
            return {
                "success": False,
                "message": message
            }

        refreshed_lottery_result = api.get_daily_lottery_info(refreshed_page_info_result["data"])
        if not refreshed_lottery_result["success"]:
            message = f"鍒锋柊鍚庣殑绛惧埌澶╂暟瑙ｆ瀽澶辫触: {refreshed_lottery_result['error']}"
            reward_claim["message"] = message
            return {
                "success": False,
                "message": message
            }
        refreshed_fragment_result = api.get_fragment_collect_info(refreshed_page_info_result["data"])
        if not refreshed_fragment_result["success"]:
            message = f"鍒锋柊鍚庣殑棰嗗彇缁勪欢瑙ｆ瀽澶辫触: {refreshed_fragment_result['error']}"
            reward_claim["message"] = message
            return {
                "success": False,
                "message": message
            }

        sign_day = refreshed_lottery_result.get("sign_day", 0)
        result["daily_lottery"]["sign_day"] = sign_day
        signed_days = self._safe_int(refreshed_fragment_result.get("signed_days", 0))
        if signed_days < 7:
            if signed_days <= 0:
                return {
                    "success": True,
                    "message": ""
                }
            return {
                "success": True,
                "message": f"褰撳墠绛惧埌绗?{signed_days} 澶╋紝鏈埌绗?7 澶╅鍙栨潯浠?
            }

        reward_claim["attempted"] = True
        claim_logger.info("褰撳墠绛惧埌绗?7 澶╋紝寮€濮嬮鍙栧鍔?)
        receive_result = api.receive_daily_lottery_reward(
            portal_info=portal_result,
            component_number=refreshed_fragment_result["component_number"],
            component_node_id=refreshed_fragment_result["component_node_id"],
            sign_series_id=refreshed_fragment_result.get("sign_series_id", "")
        )

        if receive_result["success"]:
            reward_name = receive_result.get("reward_name", "")
            message = receive_result.get("reason")
            if not message:
                message = f"绗?澶╁鍔遍鍙栨垚鍔? {reward_name}" if reward_name else "绗?澶╁鍔遍鍙栨垚鍔?
            reward_claim["success"] = True
            reward_claim["message"] = message
            return {
                "success": True,
                "message": message
            }

        message = receive_result.get("error", "绗?澶╁鍔遍鍙栧け璐?)
        if (
            receive_result.get("error_type") == "token_expired"
            or self._is_auth_expired_message(message)
        ):
            result["auth_expired"] = True
            message = "Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?
        claim_logger.info(
            "绗?澶╁鍔遍鍙栧け璐ヨ瘖鏂? %s",
            self._format_diagnostics({
                "message": message,
                "response_data": receive_result.get("data", {}),
                "payload_summary": receive_result.get("payload_summary", {})
            })
        )

        reward_claim["success"] = False
        reward_claim["message"] = message
        return {
            "success": False,
            "message": message
        }

    def process_account(self, account_info: Dict[str, Any]) -> Dict[str, Any]:
        """澶勭悊鍗曚釜璐﹀彿鐨勫ぉ澶╅绂忓埄浠诲姟"""
        account_name = account_info.get("account_name", "鏈懡鍚嶈处鍙?)
        account_logger = bind_logger(self.logger, account=account_name)
        log_page_switch(account_logger, self.page_name)

        result = {
            "account_name": account_name,
            "success": False,
            "auth_expired": False,
            "message": "",
            "portal_info": {},
            "free_member_checkin": {
                "sign_date": "",
                "sign_status": "",
                "reward_title": "",
                "signed_days": 0,
                "sign_series_id": "",
                "message": ""
            },
            "member_trial": {
                "remain_times": 0,
                "candidates": [],
                "attempts": [],
                "message": ""
            },
            "daily_lottery": {
                "remain_times": 0,
                "session_id": "",
                "session_name": "",
                "stock_status": "",
                "sign_day": 0,
                "reward_pool": [],
                "attempts": [],
                "reward_claim": {
                    "attempted": False,
                    "success": False,
                    "message": ""
                },
                "message": ""
            }
        }

        cookies = account_info.get("cookies", "")
        user_agent = account_info.get("user_agent")
        if not cookies:
            result["message"] = "璐﹀彿閰嶇疆涓己灏?cookies"
            account_logger.error(result["message"])
            return result

        api = DailyBenefitsAPI(cookies=cookies, user_agent=user_agent)

        portal_result = api.get_benefit_portal()
        if not portal_result["success"]:
            result["message"] = portal_result["error"]
            if (
                portal_result.get("error_type") == "token_expired"
                or self._is_auth_expired_message(result["message"])
            ):
                result["auth_expired"] = True
                result["message"] = "Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?
            log_task_result(account_logger, "馃搷 鍏ュ彛鍙戠幇", f"鉂?{result['message']}")
            return result

        result["portal_info"] = {
            "title": portal_result.get("title", ""),
            "position": portal_result.get("position", ""),
            "activity_number": portal_result["activity_number"],
            "page_number": portal_result["page_number"]
        }
        log_task_result(
            account_logger,
            "馃搷 鍏ュ彛鍙戠幇",
            f"鉁?{portal_result.get('position') or portal_result.get('title') or '鏈煡鍏ュ彛'} "
            f"({portal_result['activity_number']})"
        )
        page_info_result = api.get_page_info(portal_result)
        if not page_info_result["success"]:
            result["message"] = page_info_result["error"]
            if (
                page_info_result.get("error_type") == "token_expired"
                or self._is_auth_expired_message(result["message"])
            ):
                result["auth_expired"] = True
                result["message"] = "Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?
            log_task_result(account_logger, "馃搷 鍏ュ彛鍙戠幇", f"鉂?{result['message']}")
            return result

        current_page_info = page_info_result["data"]
        initial_fragment_result = api.get_fragment_collect_info(current_page_info)
        if (
            initial_fragment_result["success"]
            and self._safe_int(initial_fragment_result.get("signed_days", 0)) >= 7
        ):
            pending_reward_status = self._claim_daily_lottery_reward_if_ready(
                api=api,
                portal_result=portal_result,
                page_info=current_page_info,
                account_name=account_name,
                result=result,
                force_claim=True,
                fragment_result=initial_fragment_result
            )
            if not pending_reward_status["success"]:
                result["success"] = False
                result["message"] = pending_reward_status["message"]
                result["daily_lottery"]["message"] = pending_reward_status["message"]
                if result["auth_expired"]:
                    result["message"] = "Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?
                log_task_result(account_logger, "馃弳 绗?澶╁鍔?, f"鉂?{result['message']}")
                return result

            if pending_reward_status["claimed"]:
                refreshed_page_info_result = api.get_page_info(portal_result)
                if refreshed_page_info_result["success"]:
                    current_page_info = refreshed_page_info_result["data"]
                else:
                    refresh_error = refreshed_page_info_result["error"]
                    result["success"] = False
                    result["message"] = f"{pending_reward_status['message']}锛屼絾鍒锋柊椤甸潰淇℃伅澶辫触: {refresh_error}"
                    result["daily_lottery"]["message"] = result["message"]
                    log_task_result(account_logger, "馃弳 绗?澶╁鍔?, f"鉂?{result['message']}")
                    return result

        fragment_collect_status = self._process_fragment_collect_sign_in(
            api=api,
            portal_result=portal_result,
            page_info=current_page_info,
            account_name=account_name,
            result=result
        )

        if fragment_collect_status["refresh_page_info"]:
            refreshed_page_info_result = api.get_page_info(portal_result)
            if refreshed_page_info_result["success"]:
                current_page_info = refreshed_page_info_result["data"]
                refreshed_fragment_result = api.get_fragment_collect_info(current_page_info)
                if refreshed_fragment_result["success"]:
                    self._sync_free_member_checkin_state(
                        result["free_member_checkin"],
                        refreshed_fragment_result
                    )
                    fragment_collect_status["message"] = self._build_free_member_checkin_message(
                        result["free_member_checkin"],
                        signed_now=fragment_collect_status.get("signed_now", False)
                    )
                    result["free_member_checkin"]["message"] = fragment_collect_status["message"]
                else:
                    refresh_error = refreshed_fragment_result["error"]
                    fragment_collect_status = {
                        "success": False,
                        "message": (
                            f"{fragment_collect_status['message']}锛?
                            f"浣嗗埛鏂板悗鐨勭鍒扮姸鎬佽В鏋愬け璐? {refresh_error}"
                        )
                    }
                    result["free_member_checkin"]["message"] = fragment_collect_status["message"]
            else:
                refresh_error = refreshed_page_info_result["error"]
                fragment_collect_status = {
                    "success": False,
                    "message": f"{fragment_collect_status['message']}锛屼絾鍒锋柊椤甸潰淇℃伅澶辫触: {refresh_error}"
                }
                result["free_member_checkin"]["message"] = fragment_collect_status["message"]

        if result["auth_expired"]:
            result["success"] = False
            result["message"] = "Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?
            log_task_result(account_logger, "馃搮 鎵撳崱绛惧埌", "鉂?Token宸茶繃鏈?)
            return result

        member_trial_status = self._process_member_trial(
            api=api,
            portal_result=portal_result,
            page_info=current_page_info,
            account_name=account_name,
            result=result
        )
        if result["auth_expired"]:
            result["success"] = False
            result["message"] = "Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?
            log_task_result(account_logger, "馃巵 浼氬憳璇曠敤", "鉂?Token宸茶繃鏈?)
            return result
        daily_lottery_status = self._process_daily_lottery(
            api=api,
            portal_result=portal_result,
            page_info=current_page_info,
            account_name=account_name,
            result=result
        )
        if result["auth_expired"]:
            result["success"] = False
            result["message"] = "Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?
            log_task_result(account_logger, "馃幇 澶╁ぉ鎶藉", "鉂?Token宸茶繃鏈?)
            return result

        result["success"] = (
            fragment_collect_status["success"]
            and member_trial_status["success"]
            and daily_lottery_status["success"]
        )
        result["message"] = " | ".join(
            message
            for message in [
                fragment_collect_status["message"],
                member_trial_status["message"],
                daily_lottery_status["message"]
            ]
            if message
        ) or "澶勭悊瀹屾垚"

        checkin_message = result["free_member_checkin"].get("message", "")
        trial_message = result["member_trial"].get("message", "")
        lottery_message = result["daily_lottery"].get("message", "")

        if checkin_message:
            checkin_status = "鉁? if "鎴愬姛" in checkin_message or "宸茬鍒? in checkin_message else "鉂?
            if "鏃? in checkin_message or "宸茬鍒? in checkin_message:
                checkin_status = "鈴? if "鏃? in checkin_message else "鉁?
            log_task_result(account_logger, "馃搮 鎵撳崱绛惧埌", f"{checkin_status} {checkin_message}")

        if trial_message:
            trial_status = "鉁? if "鎴愬姛" in trial_message else "鉂?
            if "鏃? in trial_message or "宸茶揪涓婇檺" in trial_message or "鏃犻渶閲嶅" in trial_message:
                trial_status = "鈴?
            log_task_result(account_logger, "馃巵 浼氬憳璇曠敤", f"{trial_status} {trial_message}")

        if lottery_message:
            lottery_status = "鉁? if "鎴愬姛" in lottery_message else "鉂?
            if "鏃? in lottery_message:
                lottery_status = "鈴?
            log_task_result(account_logger, "馃幇 澶╁ぉ鎶藉", f"{lottery_status} {lottery_message}")

        return result

    def run(self) -> None:
        """鎵ц鎵€鏈夎处鍙蜂换鍔?""
        self.logger.info("%s", "=" * 60)
        self.logger.info("WPS 澶╁ぉ棰嗙鍒╀换鍔″紑濮?)
        self.logger.info("%s", "=" * 60)

        if not self.accounts:
            self.logger.warning("娌℃湁鍙鐞嗙殑 WPS 璐﹀彿")
            return

        for index, account_info in enumerate(self.accounts):
            self.account_results.append(self.process_account(account_info))

            if index < len(self.accounts) - 1:
                delay = random.uniform(3, 8)
                self.logger.info("鈴憋笍  绛夊緟 %.1f 绉掑悗澶勭悊涓嬩竴涓处鍙?..", delay)
                time.sleep(delay)

        self._print_summary()
        if self.enable_notification:
            self._send_notification()

    @staticmethod
    def build_notification_lines(item: Dict[str, Any]) -> List[str]:
        """鏋勯€犲崟璐﹀彿澶╁ぉ棰嗙鍒╅€氱煡鍐呭銆?""
        lines = [f"    [{DailyBenefitsTasks.page_name}] {item.get('message', '')}"]

        free_member_checkin = item.get("free_member_checkin", {})
        if free_member_checkin.get("message"):
            lines.append(f"      鎵撳崱鍏嶈垂棰嗕細鍛? {free_member_checkin.get('message', '')}")

        member_trial = item.get("member_trial", {})
        lines.append(f"      鍓╀綑璇曠敤鐢宠娆℃暟: {member_trial.get('remain_times', 0)}")
        attempts = member_trial.get("attempts", [])
        if attempts:
            lines.append("      璇曠敤鐢宠缁撴灉:")
            for attempt in attempts:
                attempt_status = "鎴愬姛" if attempt["success"] else "澶辫触"
                lines.append(f"        {attempt_status} - {attempt['title']}: {attempt['message']}")

        daily_lottery = item.get("daily_lottery", {})
        lines.append(f"      鍓╀綑鎶藉娆℃暟: {daily_lottery.get('remain_times', 0)}")
        if daily_lottery.get("sign_day"):
            lines.append(f"      褰撳墠绛惧埌澶╂暟: 绗?{daily_lottery.get('sign_day')} 澶?)
        lottery_attempts = daily_lottery.get("attempts", [])
        if lottery_attempts:
            lines.append("      鎶藉缁撴灉:")
            for attempt in lottery_attempts:
                attempt_status = "鎴愬姛" if attempt["success"] else "澶辫触"
                lines.append(f"        绗瑊attempt['index']}娆?{attempt_status}: {attempt['message']}")
        reward_claim = daily_lottery.get("reward_claim", {})
        if reward_claim.get("message"):
            claim_status = "鎴愬姛" if reward_claim.get("success") else "澶辫触"
            if not reward_claim.get("attempted"):
                claim_status = "璺宠繃"
            lines.append(f"      绗?澶╁鍔遍鍙? {claim_status} - {reward_claim.get('message', '')}")

        return lines

    def _print_summary(self) -> None:
        """鎵撳嵃浠诲姟缁熻"""
        self.logger.info("%s", "=" * 60)
        self.logger.info("鎵ц缁撴灉缁熻")
        self.logger.info("%s", "=" * 60)

        total = len(self.account_results)
        success = sum(1 for item in self.account_results if item["success"])
        failed = total - success

        self.logger.info("鎬昏处鍙锋暟: %s", total)
        self.logger.info("鎵ц鎴愬姛: %s", success)
        self.logger.info("鎵ц澶辫触: %s", failed)

        for item in self.account_results:
            status = "鉁?鎴愬姛" if item["success"] else "鉂?澶辫触"
            self.logger.info("%s: %s - %s", item["account_name"], status, item["message"])

        self.logger.info("%s", "=" * 60)

    def _send_notification(self) -> None:
        """鍙戦€佺粨鏋滈€氱煡"""
        if not self.account_results:
            return

        total = len(self.account_results)
        success = sum(1 for item in self.account_results if item["success"])
        failed = total - success

        content_lines = [
            f"馃搳 鎬昏处鍙锋暟: {total}",
            f"鉁?鎵ц鎴愬姛: {success}",
            f"鉂?鎵ц澶辫触: {failed}",
            "",
            "馃搵 璇︾粏缁撴灉:"
        ]

        for item in self.account_results:
            status = "鉁? if item["success"] else "鉂?
            content_lines.append(f"{status} {item['account_name']}: {item['message']}")

            portal_info = item.get("portal_info", {})
            if portal_info:
                content_lines.append(
                    f"    馃幆 娲诲姩椤? {portal_info.get('activity_number', '')} / {portal_info.get('page_number', '')}"
                )

            free_member_checkin = item.get("free_member_checkin", {})
            if free_member_checkin.get("message"):
                content_lines.append(f"    馃搮 鎵撳崱鍏嶈垂棰嗕細鍛? {free_member_checkin.get('message', '')}")

            member_trial = item.get("member_trial", {})
            remain_times = member_trial.get("remain_times", 0)
            content_lines.append(f"    馃啌 鍓╀綑璇曠敤鐢宠娆℃暟: {remain_times}")

            attempts = member_trial.get("attempts", [])
            if attempts:
                content_lines.append("    馃摑 鐢宠缁撴灉:")
                for attempt in attempts:
                    attempt_status = "鎴愬姛" if attempt["success"] else "澶辫触"
                    content_lines.append(
                        f"       {attempt_status} - {attempt['title']}: {attempt['message']}"
                    )

            daily_lottery = item.get("daily_lottery", {})
            content_lines.append(f"    馃幇 鍓╀綑鎶藉娆℃暟: {daily_lottery.get('remain_times', 0)}")
            if daily_lottery.get("sign_day"):
                content_lines.append(f"    馃搯 褰撳墠绛惧埌澶╂暟: 绗?{daily_lottery.get('sign_day')} 澶?)

            lottery_attempts = daily_lottery.get("attempts", [])
            if lottery_attempts:
                content_lines.append("    馃巵 鎶藉缁撴灉:")
                for attempt in lottery_attempts:
                    attempt_status = "鎴愬姛" if attempt["success"] else "澶辫触"
                    content_lines.append(
                        f"       绗瑊attempt['index']}娆?{attempt_status}: {attempt['message']}"
                    )

            reward_claim = daily_lottery.get("reward_claim", {})
            if reward_claim.get("message"):
                claim_status = "鎴愬姛" if reward_claim.get("success") else "澶辫触"
                if not reward_claim.get("attempted"):
                    claim_status = "璺宠繃"
                content_lines.append(
                    f"    馃弳 绗?澶╁鍔遍鍙? {claim_status} - {reward_claim.get('message', '')}"
                )

            if item != self.account_results[-1]:
                content_lines.append("")

        try:
            send_notification(
                title="WPS 澶╁ぉ棰嗙鍒╃粨鏋滈€氱煡",
                content="\n".join(content_lines),
                sound=NotificationSound.BIRDSONG
            )
            self.logger.info("鉁?鎺ㄩ€侀€氱煡宸插彂閫?)
        except Exception as exc:
            self.logger.warning("鈿狅笍 鍙戦€佹帹閫侀€氱煡澶辫触: %s", exc)


def main() -> None:
    """涓诲嚱鏁?""
    try:
        DailyBenefitsTasks().run()
    except FileNotFoundError as exc:
        print(f"鉂?閿欒: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"鉂?鍙戠敓鏈煡閿欒: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
