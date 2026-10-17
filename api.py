#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WPS API妯″潡

鎻愪緵WPS绛惧埌鐩稿叧鐨凙PI鎺ュ彛鍜屽姞瀵嗗姛鑳?"""

import base64
import time
import random
import string
import requests
import json
import logging
from typing import Dict, Optional
from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class WPSEncryption:
    """WPS鍔犲瘑宸ュ叿绫?""

    @staticmethod
    def generate_aes_key(length: int = 32) -> str:
        """
        鐢熸垚AES瀵嗛挜: 闅忔満瀛楃 + 鏃堕棿鎴?
        Args:
            length (int): 瀵嗛挜闀垮害锛岄粯璁?2浣?
        Returns:
            str: 鐢熸垚鐨凙ES瀵嗛挜
        """
        chars = string.ascii_lowercase + string.digits
        random_part = ''.join(random.choice(chars) for _ in range(length - 10))
        timestamp_part = str(int(time.time()))
        return random_part + timestamp_part

    @staticmethod
    def aes_encrypt(plain_text: str, aes_key: str) -> str:
        """
        AES-CBC鍔犲瘑

        Args:
            plain_text (str): 鏄庢枃鏂囨湰
            aes_key (str): AES瀵嗛挜

        Returns:
            str: Base64缂栫爜鐨勫姞瀵嗙粨鏋?        """
        # 灏嗗瘑閽ヨ浆涓篵ytes骞堕浂濉厖鍒?2瀛楄妭
        key_bytes = aes_key.encode('utf-8')
        key_padded = key_bytes + b'\x00' * (32 - len(key_bytes))

        # 浣跨敤鍓?6浣嶄綔涓篒V
        iv = aes_key[:16].encode('utf-8')

        # 鍒涘缓AES鍔犲瘑鍣?(CBC妯″紡)
        cipher = AES.new(key_padded, AES.MODE_CBC, iv)

        # PKCS7濉厖
        plain_bytes = plain_text.encode('utf-8')
        padded_data = pad(plain_bytes, AES.block_size)

        # 鍔犲瘑骞惰繑鍥濨ase64
        encrypted = cipher.encrypt(padded_data)
        return base64.b64encode(encrypted).decode('utf-8')

    @staticmethod
    def rsa_encrypt(plain_text: str, public_key_pem: str) -> str:
        """
        RSA鍔犲瘑

        Args:
            plain_text (str): 鏄庢枃鏂囨湰
            public_key_pem (str): PEM鏍煎紡鐨凴SA鍏挜

        Returns:
            str: Base64缂栫爜鐨勫姞瀵嗙粨鏋?        """
        public_key = RSA.import_key(public_key_pem)
        cipher = PKCS1_v1_5.new(public_key)
        encrypted = cipher.encrypt(plain_text.encode('utf-8'))
        return base64.b64encode(encrypted).decode('utf-8')


class WPSAPI:
    """WPS API绫?""

    def __init__(self, cookies: str, user_agent: Optional[str] = None):
        """
        鍒濆鍖朅PI绫?
        Args:
            cookies (str): Cookie瀛楃涓?            user_agent (Optional[str]): 鐢ㄦ埛浠ｇ悊瀛楃涓诧紝鍙€?        """
        self.cookies = self._parse_cookies(cookies)
        self.user_agent = user_agent or (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
        )
        self.base_headers = {
            'User-Agent': self.user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/json',
            'pragma': 'no-cache',
            'cache-control': 'no-cache',
            'sec-ch-ua-platform': '"macOS"',
            'sec-ch-ua': '"Chromium";v="142", "Brave";v="142", "Not_A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-gpc': '1',
            'accept-language': 'zh-CN,zh;q=0.9',
            'origin': 'https://personal-act.wps.cn',
            'sec-fetch-site': 'same-site',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
            'referer': 'https://personal-act.wps.cn/',
            'priority': 'u=1, i'
        }
        self.encrypt_key_url = 'https://personal-bus.wps.cn/sign_in/v1/encrypt/key'
        self.sign_in_url = 'https://personal-bus.wps.cn/sign_in/v1/sign_in'
        self.lottery_url = 'https://personal-act.wps.cn/activity-rubik/activity/component_action'
        self.user_info_url = 'https://personal-act.wps.cn/activity-rubik/activity/page_info'
        self.encryption = WPSEncryption()

    @staticmethod
    def _parse_cookies(cookie_str: str) -> Dict[str, str]:
        """
        瑙ｆ瀽Cookie瀛楃涓蹭负瀛楀吀

        Args:
            cookie_str (str): Cookie瀛楃涓?
        Returns:
            Dict[str, str]: Cookie瀛楀吀
        """
        cookies = {}
        for item in cookie_str.split('; '):
            if '=' in item:
                key, value = item.split('=', 1)
                cookies[key] = value
        return cookies

    def get_user_info(self, activity_number: str = "HD2025031821201822",
                      page_number: str = "YM2025041617143388") -> Dict:
        """
        鑾峰彇鐢ㄦ埛涓汉淇℃伅锛屽寘鎷娊濂栨鏁板拰绉垎

        Args:
            activity_number (str): 娲诲姩缂栧彿
            page_number (str): 椤甸潰缂栧彿

        Returns:
            Dict: 鐢ㄦ埛淇℃伅缁撴灉
                {
                    'success': bool,           # 鏄惁鎴愬姛
                    'lottery_times': int,      # 鎶藉娆℃暟
                    'points': int,             # 褰撳墠绉垎
                    'advent_points': int,      # 鍗冲皢杩囨湡绉垎
                    'lottery_component_number': str,  # 鎶藉缁勪欢缂栧彿
                    'lottery_component_node_id': str, # 鎶藉缁勪欢鑺傜偣ID
                    'points_component_number': str,   # 绉垎缁勪欢缂栧彿
                    'points_component_node_id': str,  # 绉垎缁勪欢鑺傜偣ID
                    'raw_data': dict,          # 鍘熷杩斿洖鏁版嵁
                    'error': str               # 澶辫触鏃剁殑閿欒淇℃伅
                }
        """
        logger.info("姝ｅ湪鑾峰彇鐢ㄦ埛涓汉淇℃伅...")

        try:
            # 鏋勯€犺姹傚ご
            headers = self.base_headers.copy()
            headers['referer'] = f'https://personal-act.wps.cn/rubik2/portal/{activity_number}/{page_number}?cs_from=&mk_key=JkVKsOtv4aCLMdNdAKwUGoz9tfKeFZVKyjEe&position=mac_grzx_sign'
            headers['sec-fetch-site'] = 'same-origin'
            headers['sec-fetch-mode'] = 'cors'
            headers['sec-fetch-dest'] = 'empty'

            # 鏋勯€犺姹傚弬鏁?            params = {
                'activity_number': activity_number,
                'page_number': page_number
            }

            # 鍙戦€丟ET璇锋眰
            response = requests.get(
                self.user_info_url,
                headers=headers,
                cookies=self.cookies,
                params=params,
                timeout=30
            )

            logger.debug(f"鐢ㄦ埛淇℃伅璇锋眰URL: {response.url}")
            logger.debug(f"鐢ㄦ埛淇℃伅鍝嶅簲鐘舵€佺爜: {response.status_code}")
            logger.debug(f"鐢ㄦ埛淇℃伅鍝嶅簲鍐呭: {response.text}")

            response.raise_for_status()
            result = response.json()

            if result.get('result') == 'ok' and 'data' in result:
                data_list = result.get('data', [])

                # 鍒濆鍖栬繑鍥炵粨鏋?                user_info = {
                    'success': True,
                    'lottery_times': 0,
                    'points': 0,
                    'advent_points': 0,
                    'lottery_component_number': '',
                    'lottery_component_node_id': '',
                    'points_component_number': '',
                    'points_component_node_id': '',
                    'raw_data': result
                }

                # 閬嶅巻data鍒楄〃鏌ユ壘鎶藉鍜岀Н鍒嗕俊鎭?                for item in data_list:
                    item_type = item.get('type')

                    # type 45 鏄娊濂栦俊鎭?                    if item_type == 45 and 'lottery_v2' in item:
                        lottery_v2 = item.get('lottery_v2', {})
                        lottery_list = lottery_v2.get('lottery_list', [])

                        # 鏌ユ壘杩涜涓殑鎶藉浼氳瘽
                        for lottery_session in lottery_list:
                            if lottery_session.get('session_status') == 'IN_PROGRESS':
                                user_info['lottery_times'] = lottery_session.get('times', 0)
                                user_info['lottery_component_number'] = item.get('number', '')
                                user_info['lottery_component_node_id'] = item.get('component_node_id', '')
                                logger.info(f"鉁?鑾峰彇鍒版娊濂栦俊鎭? 鍓╀綑娆℃暟 {user_info['lottery_times']} 娆?)
                                break

                    # type 36 鏄Н鍒嗕俊鎭?                    elif item_type == 36 and 'task_center_user_info' in item:
                        task_center = item.get('task_center_user_info', {})
                        user_info['points'] = task_center.get('integral', 0)
                        user_info['advent_points'] = task_center.get('advent_integral', 0)
                        user_info['points_component_number'] = item.get('number', '')
                        user_info['points_component_node_id'] = item.get('component_node_id', '')
                        logger.info(f"鉁?鑾峰彇鍒扮Н鍒嗕俊鎭? 褰撳墠绉垎 {user_info['points']}, 鍗冲皢杩囨湡 {user_info['advent_points']}")

                logger.info("鉁?鎴愬姛鑾峰彇鐢ㄦ埛涓汉淇℃伅")
                return user_info
            else:
                error_msg = result.get('msg', '鏈煡閿欒')
                logger.error(f"鉂?鑾峰彇鐢ㄦ埛淇℃伅澶辫触: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }

        except requests.exceptions.RequestException as e:
            error_msg = f"缃戠粶璇锋眰澶辫触: {str(e)}"
            logger.error(f"鉂?{error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"鏈煡閿欒: {str(e)}"
            logger.error(f"鉂?{error_msg}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': error_msg
            }


    def get_encrypt_key(self) -> Dict:
        """
        鑾峰彇RSA鍔犲瘑鍏挜

        Returns:
            Dict: 鍖呭惈鍏挜淇℃伅鐨勫瓧鍏?                {
                    'success': bool,  # 鏄惁鎴愬姛
                    'public_key': str,  # 鎴愬姛鏃剁殑鍏挜(Base64缂栫爜)
                    'error': str      # 澶辫触鏃剁殑閿欒淇℃伅
                }
        """
        logger.info("姝ｅ湪鑾峰彇RSA鍔犲瘑鍏挜...")

        try:
            response = requests.get(
                self.encrypt_key_url,
                headers=self.base_headers,
                cookies=self.cookies,
                timeout=30
            )
            response.raise_for_status()

            result = response.json()

            if result.get('result') == 'ok' and 'data' in result:
                public_key_base64 = result['data']
                logger.info("鉁?鎴愬姛鑾峰彇RSA鍔犲瘑鍏挜")
                return {
                    'success': True,
                    'public_key': public_key_base64
                }
            else:
                error_msg = result.get('msg', '鏈煡閿欒')
                logger.error(f"鉂?鑾峰彇鍏挜澶辫触: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }

        except requests.exceptions.RequestException as e:
            error_msg = f"缃戠粶璇锋眰澶辫触: {str(e)}"
            logger.error(f"鉂?{error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"鏈煡閿欒: {str(e)}"
            logger.error(f"鉂?{error_msg}")
            return {
                'success': False,
                'error': error_msg
            }

    def generate_crypto_data(self, public_key_base64: str, user_id: int, platform: int = 64) -> Dict:
        """
        鐢熸垚鍔犲瘑鏁版嵁鍜宼oken

        Args:
            public_key_base64 (str): Base64缂栫爜鐨凴SA鍏挜
            user_id (int): 鐢ㄦ埛ID锛堝繀闇€锛?            platform (int): 骞冲彴鏍囪瘑锛岄粯璁?4

        Returns:
            Dict: 鍖呭惈鍔犲瘑鏁版嵁鐨勫瓧鍏?                {
                    'extra': str,      # AES鍔犲瘑鐨勬暟鎹?                    'token': str,      # RSA鍔犲瘑鐨凙ES瀵嗛挜
                    'aesKey': str      # AES瀵嗛挜锛堢敤浜庤皟璇曪級
                }
        """

        # 瑙ｇ爜鍏挜
        public_key_pem = base64.b64decode(public_key_base64).decode('utf-8')

        # 鐢熸垚AES瀵嗛挜
        aes_key = self.encryption.generate_aes_key(32)

        # 鍑嗗鏄庢枃鏁版嵁
        plain_data = json.dumps({
            "user_id": user_id,
            "platform": platform
        }, separators=(',', ':'))

        # AES鍔犲瘑鏁版嵁 (杩欐槸extra)
        encrypt_data = self.encryption.aes_encrypt(plain_data, aes_key)

        # RSA鍔犲瘑AES瀵嗛挜 (杩欐槸璇锋眰澶翠腑鐨則oken)
        token = self.encryption.rsa_encrypt(aes_key, public_key_pem)

        logger.debug(f"User ID: {user_id}")
        logger.debug(f"Plain Data: {plain_data}")
        logger.debug(f"AES Key: {aes_key}")
        logger.debug(f"Extra: {encrypt_data}")
        logger.debug(f"Token (璇锋眰澶?: {token}")

        return {
            "extra": encrypt_data,
            "token": token,
            "aesKey": aes_key
        }

    def sign_in(self, user_id: int) -> Dict:
        """
        鎵ц绛惧埌

        Args:
            user_id (int): 鐢ㄦ埛ID锛堝繀闇€锛?
        Returns:
            Dict: 绛惧埌缁撴灉
                {
                    'success': bool,  # 鏄惁鎴愬姛
                    'data': dict,     # 鎴愬姛鏃剁殑绛惧埌淇℃伅
                    'error': str      # 澶辫触鏃剁殑閿欒淇℃伅
                }
        """
        logger.info("寮€濮嬬鍒?..")

        try:
            # 1. 鑾峰彇RSA鍏挜
            key_result = self.get_encrypt_key()
            if not key_result['success']:
                return {
                    'success': False,
                    'error': f"鑾峰彇鍏挜澶辫触: {key_result['error']}"
                }

            public_key_base64 = key_result['public_key']

            # 2. 鐢熸垚鍔犲瘑鏁版嵁鍜宼oken
            crypto_result = self.generate_crypto_data(public_key_base64, user_id)

            # 3. 鏋勯€犺姹傚ご (浣跨敤鐢熸垚鐨則oken)
            headers = self.base_headers.copy()
            headers['token'] = crypto_result['token']

            # 4. 鏋勯€犺姹傛暟鎹?            data = {
                "encrypt": True,
                "extra": crypto_result['extra'],
                "pay_origin": "pc_ucs_rwzx_sign"
            }

            logger.debug(f"璇锋眰URL: {self.sign_in_url}")
            logger.debug(f"璇锋眰澶碩oken: {crypto_result['token'][:50]}...")
            logger.debug(f"璇锋眰鏁版嵁: {json.dumps(data, indent=2)}")

            # 5. 鍙戦€佽姹?            response = requests.post(
                self.sign_in_url,
                headers=headers,
                cookies=self.cookies,
                json=data,
                timeout=30
            )

            logger.debug(f"鍝嶅簲鐘舵€佺爜: {response.status_code}")
            logger.debug(f"鍝嶅簲鍐呭: {response.text}")

            # 6. 瑙ｆ瀽鍝嶅簲
            if response.status_code == 200:
                resp_data = response.json()
                if resp_data.get('result') == 'ok':
                    logger.info("鉁?绛惧埌鎴愬姛!")
                    return {
                        'success': True,
                        'data': resp_data.get('data', {})
                    }
                else:
                    error_msg = resp_data.get('msg', '鏈煡閿欒')
                    error_code = resp_data.get('code')
                    ext_msg = resp_data.get('ext_msg', '')

                    # 妫€鏌ユ槸鍚︽槸token杩囨湡
                    if error_code == 2000000 and ext_msg == 'userNotLogin':
                        logger.error("鉂?Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?)
                        return {
                            'success': False,
                            'error': 'Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?,
                            'error_type': 'token_expired'
                        }
                    # 妫€鏌ユ槸鍚﹀凡缁忕鍒?                    elif error_msg == 'has sign':
                        logger.info("鉁?浠婃棩宸茬鍒?)
                        return {
                            'success': True,
                            'already_signed': True,
                            'data': resp_data.get('data', {}),
                            'message': '浠婃棩宸茬鍒?
                        }
                    else:
                        logger.error(f"鉂?绛惧埌澶辫触: {error_msg}")
                        return {
                            'success': False,
                            'error': error_msg
                        }
            else:
                error_msg = f"HTTP {response.status_code}"
                logger.error(f"鉂?璇锋眰澶辫触: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }

        except requests.exceptions.RequestException as e:
            error_msg = f"缃戠粶璇锋眰澶辫触: {str(e)}"
            logger.error(f"鉂?{error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"鏈煡閿欒: {str(e)}"
            logger.error(f"鉂?{error_msg}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': error_msg
            }

    def lottery(self, activity_number: str = "HD2025031821201822",
                    page_number: str = "YM2025041617143388",
                    component_number: str = "ZJ2025092916515917",
                    component_node_id: str = "FN1762346087mJlk",
                    session_id: int = 2) -> Dict:
            """
            鎵ц鎶藉
            Args:
                activity_number (str): 娲诲姩缂栧彿
                page_number (str): 椤甸潰缂栧彿
                component_number (str): 缁勪欢缂栧彿
                component_node_id (str): 缁勪欢鑺傜偣ID
                session_id (int): 浼氳瘽ID锛岄粯璁?
            Returns:
                Dict: 鎶藉缁撴灉
                    {
                        'success': bool,           # 鏄惁鎴愬姛
                        'prize_name': str,         # 濂栧搧鍚嶇О
                        'reward_type': str,        # 濂栧搧绫诲瀷
                        'order_id': str,           # 璁㈠崟ID
                        'reward_id': int,          # 濂栧搧ID
                        'img': str,                # 濂栧搧鍥剧墖
                        'data': dict,              # 鍘熷杩斿洖鏁版嵁
                        'error': str,              # 澶辫触鏃剁殑閿欒淇℃伅
                        'error_type': str          # 閿欒绫诲瀷锛堝token_expired锛?                    }
            """
            logger.info("姝ｅ湪鎵ц鎶藉...")
            try:
                # 鏋勯€犺姹傚ご
                headers = self.base_headers.copy()
                headers['referer'] = f'https://personal-act.wps.cn/rubik2/portal/{activity_number}/{page_number}?cs_from=&mk_key=JkVKsOtv4aCLMdNdAKwUGoz9tfKeFZVKyjEe&position=mac_grzx_sign'
                headers['sec-fetch-site'] = 'same-origin'
                headers['sec-fetch-mode'] = 'cors'
                headers['sec-fetch-dest'] = 'empty'
                # 鏋勯€犺姹傛暟鎹?                data = {
                    "component_uniq_number": {
                        "activity_number": activity_number,
                        "page_number": page_number,
                        "component_number": component_number,
                        "component_node_id": component_node_id,
                        "filter_params": {
                            "cs_from": "",
                            "mk_key": "JkVKsOtv4aCLMdNdAKwUGoz9tfKeFZVKyjEe",
                            "position": "mac_grzx_sign"
                        }
                    },
                    "component_type": 45,
                    "component_action": "lottery_v2.exec",
                    "lottery_v2": {
                        "session_id": session_id
                    }
                }
                logger.debug(f"鎶藉璇锋眰URL: {self.lottery_url}")
                logger.debug(f"鎶藉璇锋眰鏁版嵁: {json.dumps(data, indent=2, ensure_ascii=False)}")
                # 鍙戦€丳OST璇锋眰
                response = requests.post(
                    self.lottery_url,
                    headers=headers,
                    cookies=self.cookies,
                    json=data,
                    timeout=30
                )
                logger.debug(f"鎶藉鍝嶅簲鐘舵€佺爜: {response.status_code}")
                logger.debug(f"鎶藉鍝嶅簲鍐呭: {response.text}")
                response.raise_for_status()
                result = response.json()
                # 妫€鏌ュ搷搴旂粨鏋?                if result.get('result') == 'ok' and 'data' in result:
                    data_obj = result.get('data', {})
                    lottery_v2 = data_obj.get('lottery_v2', {})
                    # 妫€鏌ユ娊濂栨槸鍚︽垚鍔?                    if lottery_v2.get('success'):
                        prize_name = lottery_v2.get('reward_name', '鏈煡')
                        reward_type = lottery_v2.get('reward_type', '')
                        order_id = lottery_v2.get('order_id', '')
                        reward_id = lottery_v2.get('reward_id', 0)
                        img = lottery_v2.get('img', '')
                        logger.info(f"鉁?鎶藉鎴愬姛锛佽幏寰? {prize_name}")
                        return {
                            'success': True,
                            'prize_name': prize_name,
                            'reward_type': reward_type,
                            'order_id': order_id,
                            'reward_id': reward_id,
                            'img': img,
                            'data': lottery_v2
                        }
                    else:
                        error_code = lottery_v2.get('error_code', 0)
                        send_msg = lottery_v2.get('send_msg', '鎶藉澶辫触')
                        logger.error(f"鉂?鎶藉澶辫触: {send_msg} (閿欒鐮? {error_code})")
                        return {
                            'success': False,
                            'error': send_msg,
                            'error_code': error_code
                        }
                else:
                    error_msg = result.get('msg', '鏈煡閿欒')
                    error_code = result.get('code')
                    ext_msg = result.get('ext_msg', '')
                    # 妫€鏌ユ槸鍚︽槸token杩囨湡
                    if error_code == 2000000 and ext_msg == 'userNotLogin':
                        logger.error("鉂?Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?)
                        return {
                            'success': False,
                            'error': 'Token宸茶繃鏈燂紝璇烽噸鏂扮櫥褰?,
                            'error_type': 'token_expired'
                        }
                    else:
                        logger.error(f"鉂?鎶藉澶辫触: {error_msg}")
                        return {
                            'success': False,
                            'error': error_msg
                        }
            except requests.exceptions.RequestException as e:
                error_msg = f"缃戠粶璇锋眰澶辫触: {str(e)}"
                logger.error(f"鉂?{error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
            except Exception as e:
                error_msg = f"鏈煡閿欒: {str(e)}"
                logger.error(f"鉂?{error_msg}")
                import traceback
                traceback.print_exc()
                return {
                    'success': False,
                    'error': error_msg
                }
