#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
new Env('WPS浠诲姟涓績');
cron: 1 1 1 1 1
"""

"""
WPS 浠诲姟涓績娲诲姩鑴氭湰

璇ヨ剼鏈皢 main.py 涓綋鍓嶇殑鏍稿績涓氬姟娴佺▼鐙珛涓哄崟鐙椿鍔ㄩ〉闈紝鍖呮嫭锛?- 璇诲彇璐﹀彿閰嶇疆淇℃伅
- 鎵ц浠诲姟涓績绛惧埌
- 鑾峰彇浠诲姟涓績鐢ㄦ埛淇℃伅
- 鎵ц浠诲姟涓績鎶藉
- 鎺ㄩ€佹墽琛岀粨鏋?
Author: Assistant
Date: 2026-03-11
"""

import json
import logging
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from api import WPSAPI
from logging_utils import (
    bind_logger,
    configure_logging,
    get_logger,
    log_page_switch,
    log_task_result,
)

# 鑾峰彇椤圭洰鏍圭洰褰?project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from notification import send_notification, NotificationSound


class WPSTaskCenterPage:
    """WPS 浠诲姟涓績娲诲姩鎵ц鍣?""

    page_name = "浠诲姟涓績"

    def __init__(self, config_path: str = None, enable_notification: bool = True, load_accounts: bool = True):
        if config_path is None:
            self.config_path = project_root / "config" / "token.json"
        else:
            self.config_path = Path(config_path)

        self.enable_notification = enable_notification
        self.accounts: List[Dict[str, Any]] = []
        self.account_results: List[Dict[str, Any]] = []
        self.logger = self._setup_logger()
        if load_accounts:
            self._init_accounts()

    def _setup_logger(self) -> logging.Logger:
        configure_logging()
        return bind_logger(get_logger("task_center"), page=self.page_name)

    def _init_accounts(self) -> None:
        """浠庨厤缃枃浠朵腑璇诲彇 WPS 璐﹀彿淇℃伅"""
        if not self.config_path.exists():
            self.logger.error("閰嶇疆鏂囦欢涓嶅瓨鍦? %s", self.config_path)
            raise FileNotFoundError(f"閰嶇疆鏂囦欢涓嶅瓨鍦? {self.config_path}")

        try:
            with open(self.config_path, "r", encoding="utf-8") as file:
                config_data = json.load(file)
        except json.JSONDecodeError as exc:
            self.logger.error("閰嶇疆鏂囦欢 JSON 瑙ｆ瀽澶辫触: %s", exc)
            raise
        except Exception as exc:
            self.logger.error("璇诲彇閰嶇疆鏂囦欢澶辫触: %s", exc)
            raise

        wps_config = config_data.get("wps", {})
        self.accounts = wps_config.get("accounts", [])

        if self.accounts:
            self.logger.info("鎴愬姛鍔犺浇 %s 涓处鍙烽厤缃?, len(self.accounts))
        else:
            self.logger.warning("閰嶇疆鏂囦欢涓病鏈夋壘鍒?wps 璐﹀彿淇℃伅")

    @staticmethod
    def _is_auth_expired_message(message: str) -> bool:
        keywords = ("Token宸茶繃鏈?, "ErrNotLogin", "userNotLogin", "鏈櫥褰?, "璇烽噸鏂扮櫥褰?)
        return any(keyword in str(message) for keyword in keywords)

    def process_account(self, account_info: Dict[str, Any]) -> Dict[str, Any]:
        """澶勭悊鍗曚釜璐﹀彿鐨勪换鍔′腑蹇冧换鍔?""
        account_name = account_info.get("account_name", "鏈懡鍚嶈处鍙?)
        account_logger = bind_logger(self.logger, account=account_name)
        log_page_switch(account_logger, self.page_name)

        result = {
            "account_name": account_name,
            "success": False,
            "auth_expired": False,
            "message": "",
            "sign_info": {},
            "sign_rewards": [],
            "lottery_info": {},
            "user_info": {},
            "final_user_info": {}
        }

        try:
            user_id = account_info.get("user_id")
            cookies = account_info.get("cookies", "")
            user_agent = account_info.get("user_agent")

            if not user_id:
                result["message"] = "璐﹀彿閰嶇疆涓己灏?user_id锛岃烦杩囦换鍔′腑蹇冪鍒?
                account_logger.warning(result["message"])
                return result

            if not cookies:
                result["message"] = "璐﹀彿閰嶇疆涓己灏?cookies"
                account_logger.error(result["message"])
                return result

            api = WPSAPI(cookies=cookies, user_agent=user_agent)

            sign_result = api.sign_in(user_id=user_id)
            if not sign_result["success"]:
                error_type = sign_result.get("error_type", "")
                error_msg = sign_result.get("error", "浠诲姟涓績绛惧埌澶辫触")
                if error_type == "token_expired":
                    result["auth_expired"] = True
                    result["message"] = "Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?
                    log_task_result(account_logger, "馃攼 绛惧埌", "鉂?Token宸茶繃鏈?)
                else:
                    result["message"] = error_msg
                    log_task_result(account_logger, "馃攼 绛惧埌", f"鉂?{error_msg}")
                return result

            result["success"] = True
            result["sign_info"] = sign_result.get("data", {}) or {}
            if sign_result.get("already_signed"):
                result["message"] = "浠诲姟涓績浠婃棩宸茬鍒?
                log_task_result(account_logger, "馃攼 绛惧埌", "鉁?浠婃棩宸茬鍒?)
            else:
                result["message"] = "浠诲姟涓績绛惧埌鎴愬姛"
                log_task_result(account_logger, "馃攼 绛惧埌", "鉁?绛惧埌鎴愬姛")

                rewards = result["sign_info"].get("rewards", [])
                reward_names = [
                    reward.get("reward_name", "")
                    for reward in rewards
                    if reward.get("reward_name")
                ]
                result["sign_rewards"] = reward_names

            user_info_result = api.get_user_info()
            if user_info_result["success"]:
                result["user_info"] = user_info_result
            else:
                if (
                    user_info_result.get("error_type") == "token_expired"
                    or self._is_auth_expired_message(user_info_result.get("error", ""))
                ):
                    result["auth_expired"] = True
                    result["message"] = "Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?
                    result["success"] = False
                    log_task_result(account_logger, "馃拵 绉垎", "鉂?Token宸茶繃鏈?)
                    return result
                log_task_result(
                    account_logger,
                    "馃拵 绉垎",
                    f"鈿?鑾峰彇澶辫触: {user_info_result.get('error', '鑾峰彇鐢ㄦ埛淇℃伅澶辫触')}"
                )

            lottery_times = result["user_info"].get("lottery_times", 0)
            component_number = result["user_info"].get("lottery_component_number", "ZJ2025092916515917")
            component_node_id = result["user_info"].get("lottery_component_node_id", "FN1762346087mJlk")

            default_max_lottery = 5
            max_lottery_limit = account_info.get("max_lottery_limit")
            if max_lottery_limit is None:
                max_lottery_limit = default_max_lottery
                is_custom_limit = False
            else:
                is_custom_limit = True

            actual_lottery_times = min(lottery_times, max_lottery_limit)
            if lottery_times > 0:
                lottery_results = []
                prize_list = []

                for index in range(actual_lottery_times):
                    delay = random.uniform(1, 3)
                    time.sleep(delay)

                    lottery_result = api.lottery(
                        component_number=component_number,
                        component_node_id=component_node_id
                    )
                    lottery_results.append(lottery_result)

                    if lottery_result["success"]:
                        prize_name = lottery_result.get("prize_name", "鏈煡濂栧搧")
                        prize_list.append(prize_name)
                    else:
                        error_type = lottery_result.get("error_type", "")
                        error_msg = lottery_result.get("error", "浠诲姟涓績鎶藉澶辫触")
                        if error_type == "token_expired" or self._is_auth_expired_message(error_msg):
                            result["auth_expired"] = True
                            result["message"] = "Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?
                            result["success"] = False
                            result["lottery_info"] = {
                                "total_attempts": len(lottery_results),
                                "successful_draws": len([item for item in lottery_results if item["success"]]),
                                "results": lottery_results,
                                "prizes": prize_list
                            }
                            log_task_result(account_logger, "馃幇 鎶藉", "鉂?Token宸茶繃鏈?)
                            return result
                        log_task_result(account_logger, "馃幇 鎶藉", f"鉂?{error_msg}")

                result["lottery_info"] = {
                    "total_attempts": actual_lottery_times,
                    "successful_draws": len([item for item in lottery_results if item["success"]]),
                    "results": lottery_results,
                    "prizes": prize_list
                }

                if prize_list:
                    log_task_result(account_logger, "馃幇 鎶藉", f"鉁?{', '.join(prize_list)}")
                else:
                    log_task_result(account_logger, "馃幇 鎶藉", "鈿?鏈腑濂?)
            else:
                log_task_result(account_logger, "馃幇 鎶藉", "鈴?鏃犲彲鐢ㄦ鏁?)

            final_user_info = api.get_user_info()
            if final_user_info["success"]:
                result["final_user_info"] = final_user_info
                log_task_result(account_logger, "馃拵 绉垎", f"{final_user_info.get('points', 0)} pt")
            else:
                if (
                    final_user_info.get("error_type") == "token_expired"
                    or self._is_auth_expired_message(final_user_info.get("error", ""))
                ):
                    result["auth_expired"] = True
                    result["message"] = "Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?
                    result["success"] = False
                    log_task_result(account_logger, "馃拵 绉垎", "鉂?Token宸茶繃鏈?)
                    return result
                log_task_result(account_logger, "馃拵 绉垎", "鈿?鑾峰彇澶辫触")

        except Exception as exc:
            result["success"] = False
            result["message"] = f"澶勭悊浠诲姟涓績璐﹀彿鏃跺彂鐢熷紓甯? {exc}"
            account_logger.error(result["message"])
            import traceback
            traceback.print_exc()

        return result

    @staticmethod
    def build_notification_lines(result: Dict[str, Any]) -> List[str]:
        """鏋勯€犲崟璐﹀彿浠诲姟涓績閫氱煡鍐呭銆?""
        lines = [f"    [{WPSTaskCenterPage.page_name}] {result.get('message', '')}"]

        sign_rewards = result.get("sign_rewards", [])
        if sign_rewards:
            lines.append(f"      绛惧埌濂栧姳: {', '.join(sign_rewards)}")

        lottery_info = result.get("lottery_info", {})
        lottery_results = lottery_info.get("results", [])
        if lottery_results:
            lines.append("      鎶藉缁撴灉:")
            for index, single_result in enumerate(lottery_results, start=1):
                if single_result["success"]:
                    prize_name = single_result.get("prize_name", "鏈煡")
                    lines.append(f"        绗瑊index}娆? {prize_name}")
                else:
                    error_msg = single_result.get("error", "鎶藉澶辫触")
                    lines.append(f"        绗瑊index}娆? {error_msg}")

        final_info = result.get("final_user_info", {}) or {}
        if final_info.get("success"):
            lines.append(
                f"      璐︽埛淇℃伅: 鎶藉娆℃暟 {final_info.get('lottery_times', 0)} | "
                f"绉垎 {final_info.get('points', 0)} | 鍗冲皢杩囨湡 {final_info.get('advent_points', 0)}"
            )

        return lines

    def run(self) -> None:
        """鎵ц鎵€鏈変换鍔′腑蹇冭处鍙蜂换鍔?""
        self.logger.info("%s", "=" * 60)
        self.logger.info("WPS浠诲姟涓績浠诲姟寮€濮?)
        self.logger.info("%s", "=" * 60)

        if not self.accounts:
            self.logger.warning("娌℃湁闇€瑕佸鐞嗙殑璐﹀彿")
            return

        for index, account_info in enumerate(self.accounts):
            self.account_results.append(self.process_account(account_info))
            if index < len(self.accounts) - 1:
                delay = random.uniform(5, 10)
                self.logger.info("绛夊緟 %.1f 绉掑悗澶勭悊涓嬩竴涓处鍙?..", delay)
                time.sleep(delay)

        self._print_summary()
        if self.enable_notification:
            self._send_notification()

    def _print_summary(self) -> None:
        """鎵撳嵃浠诲姟涓績鎵ц缁撴灉缁熻"""
        self.logger.info("%s", "=" * 60)
        self.logger.info("浠诲姟涓績鎵ц缁撴灉缁熻")
        self.logger.info("%s", "=" * 60)

        total = len(self.account_results)
        success = sum(1 for item in self.account_results if item["success"])
        failed = total - success

        self.logger.info("鎬昏处鍙锋暟: %s", total)
        self.logger.info("鎵ц鎴愬姛: %s", success)
        self.logger.info("鎵ц澶辫触: %s", failed)

        prize_summary: Dict[str, int] = {}
        total_attempts = 0
        total_successful_draws = 0

        for result in self.account_results:
            lottery_info = result.get("lottery_info")
            if not lottery_info:
                continue

            lottery_results = lottery_info.get("results", [])
            for single_result in lottery_results:
                if not single_result["success"]:
                    continue

                lottery_data = single_result.get("data", {})
                prize_name = lottery_data.get("prize_name", "鏈煡")
                if prize_name and prize_name not in {"鏈煡", "鏈腑濂?}:
                    prize_summary[prize_name] = prize_summary.get(prize_name, 0) + 1

            total_attempts += lottery_info.get("total_attempts", 0)
            total_successful_draws += lottery_info.get("successful_draws", 0)

        if total_attempts > 0:
            self.logger.info("馃搳 鎶藉缁熻: 鎬诲叡灏濊瘯 %s 娆★紝鎴愬姛 %s 娆?, total_attempts, total_successful_draws)

        if prize_summary:
            self.logger.info("馃巵 浠诲姟涓績濂栧搧缁熻:")
            for prize, count in prize_summary.items():
                self.logger.info("  %s: %s 涓?, prize, count)

        self.logger.info("璇︾粏缁撴灉:")
        for result in self.account_results:
            status = "鉁?鎴愬姛" if result["success"] else "鉂?澶辫触"
            self.logger.info("  %s: %s - %s", result["account_name"], status, result["message"])

        self.logger.info("%s", "=" * 60)

    def _send_notification(self) -> None:
        """鍙戦€佷换鍔′腑蹇冪粨鏋滈€氱煡"""
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

        for result in self.account_results:
            status = "鉁? if result["success"] else "鉂?
            content_lines.append(f"{status} {result['account_name']}: {result['message']}")

            sign_rewards = result.get("sign_rewards", [])
            if sign_rewards:
                content_lines.append(f"    馃巵 绛惧埌濂栧姳: {', '.join(sign_rewards)}")

            lottery_info = result.get("lottery_info", {})
            lottery_results = lottery_info.get("results", [])
            if lottery_results:
                content_lines.append("    馃幉 鎶藉缁撴灉:")
                for index, single_result in enumerate(lottery_results, start=1):
                    if single_result["success"]:
                        prize_name = single_result.get("prize_name", "鏈煡")
                        content_lines.append(f"       绗瑊index}娆? {prize_name}")
                    else:
                        error_msg = single_result.get("error", "鎶藉澶辫触")
                        content_lines.append(f"       绗瑊index}娆? {error_msg}")

            final_info = result.get("final_user_info", {}) or {}
            if final_info.get("success"):
                content_lines.append(
                    f"    馃搳 璐︽埛淇℃伅: 鎶藉娆℃暟 {final_info.get('lottery_times', 0)} | "
                    f"绉垎 {final_info.get('points', 0)} | 鍗冲皢杩囨湡 {final_info.get('advent_points', 0)}"
                )
            else:
                content_lines.append("    鈿狅笍 璐︽埛淇℃伅鑾峰彇澶辫触")

            if result != self.account_results[-1]:
                content_lines.append("")

        try:
            send_notification(
                title="WPS浠诲姟涓績缁撴灉閫氱煡",
                content="\n".join(content_lines),
                sound=NotificationSound.BIRDSONG
            )
            self.logger.info("鉁?浠诲姟涓績鎺ㄩ€侀€氱煡宸插彂閫?)
        except Exception as exc:
            self.logger.warning("鈿狅笍 鍙戦€佷换鍔′腑蹇冩帹閫侀€氱煡澶辫触: %s", exc)


def main() -> None:
    """涓诲嚱鏁?""
    try:
        WPSTaskCenterPage().run()
    except FileNotFoundError as exc:
        print(f"鉂?閿欒: {exc}")
        print("璇风‘淇濋厤缃枃浠跺瓨鍦ㄥ苟鍖呭惈 WPS 璐﹀彿淇℃伅")
        sys.exit(1)
    except Exception as exc:
        print(f"鉂?鍙戠敓鏈煡閿欒: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
