# -*- coding: UTF-8 -*-
import requests
import json
import time
import os
import threading
import concurrent.futures
from requests.exceptions import RequestException


from bilibili_auth import BilibiliAuth, appsign


class BiliEmoji:
    """
    用于获取B站表情包信息并保存的工具类
    """

    def __init__(self):
        # 初始化配置和认证信息
        self.PROXY = json.loads(os.getenv('PROXY', '{}'))  # 代理配置
        self.SCAN_CONFIG = json.loads(os.getenv('SCAN_CONFIG', '{"start": 1, "end": 10000, "step": 40, "ignore": [4, 250]}'))  # 扫描配置

        self.ACCOUNT = int(os.getenv('ACCOUNT', 1))  # 账号ID
        self.AUTH = BilibiliAuth(os.getenv('ACCOUNT_DB_URI', 'mongodb://localhost:27017/'))  # 认证模块
        self.ACCESS_KEY, self.COOKIE = self.AUTH.get_access(self.ACCOUNT)  # 获取访问密钥和Cookie

        self.s = requests.Session()
        self.local = threading.local()

    def get_emoji_info(self, id, session=None, retry=3):
        """
        获取表情包信息，增加重试机制。
        """
        url = 'https://api.bilibili.com/bapis/main.community.interface.emote.EmoteService/PackageDetail'
        params = {
            'access_key': '',  # 或 self.ACCESS_KEY
            'build': 8230800,
            'business': 'reply',
            'channel': 'master',
            'disable_rcmd': 0,
            'id': id,
            'mobi_app': 'android_i',
            'platform': 'android',
            'statistics': '{"appId":14,"platform":3,"version":"3.20.4","abtest":""}',
            'ts': int(time.time())
        }
        sign_params = appsign(params, 'bb3101000e232e27', '36efcfed79309338ced0380abd824ac1')
        headers = {
            'native_api_from': 'h5',
            'cookie': '',  # 或 self.COOKIE
            'accept': 'application/json, text/plain, */*',
            'referer': f'https://www.bilibili.com/h5/mall/emoji-package/detail/{id}?navhide=1&native.theme=0',
            'content-type': 'application/json',
            'user-agent': 'Mozilla/5.0 (Linux; Android 13; Mi 10 Build/TKQ1.221114.001; wv) AppleWebKit/537.36 ...',
            'bili-http-engine': 'cronet',
            'accept-encoding': 'gzip, deflate, br',
        }

        for attempt in range(retry):
            try:
                s = session or self.s
                response = s.get(url, params=sign_params, headers=headers, timeout=10)
                if response.status_code == 200:
                    res = response.json()
                    if res['code'] == 0:
                        data = res.get('data', {})
                        package = data.get('package')
                        if package:
                            return self._parse_package(package)
                        else:
                            return None
                    else:
                        print(f"[ERROR] 表情包ID {id} 获取失败: {res['message']}")
                break  # 非200响应不重试
            except RequestException as e:
                print(f"[WARN] 获取ID {id} 失败，重试 {attempt + 1}/3，错误: {e}")
                time.sleep(1)
        return None

    @staticmethod
    def _parse_package(package: dict) -> dict:
        """
        解析单个表情包信息
        :param package: 表情包数据
        :return: 解析后的表情包字典
        """
        package_dict = {
            'id': package['id'],
            'text': package['text'],
            'icon': package['url'].replace('http://', 'https://'),
            'resource_type': package.get('resource_type', 0),
        }
        if 'emotes' in package:
            emotes = []
            for emote in package['emotes']:
                emote_data = {
                    'text': emote['text'].replace('[', '').replace(']', ''),
                    'url': emote['url'].replace('http://', 'https://'),
                }
                if 'gif_url' in emote:  # 动态表情
                    emote_data['gif_url'] = emote['gif_url'].replace('http://', 'https://')
                if 'webp_url' in emote:
                    emote_data['webp_url'] = emote['webp_url'].replace('http://', 'https://')
                emotes.append(emote_data)
            package_dict['emote'] = emotes
        return package_dict

    @staticmethod
    def save_emoji_info(emoji_info: dict):
        """
        保存表情包信息到本地文件
        :param emoji_info: 表情包信息字典
        """
        emoji_id = emoji_info['id']
        emoji_text = emoji_info['text']
        filename = f'{emoji_id}-{emoji_text}.json'
        filepath = os.path.join('list', filename)
        os.makedirs('list', exist_ok=True)  # 确保目录存在
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(json.dumps(emoji_info, ensure_ascii=False, indent=2))

    def get_latest_emoji_id(self) -> int:
        """
        获取最新的表情包ID
        :return: 最新表情包ID；失败时返回 SCAN_CONFIG['end']
        """
        try:
            base_url = 'https://api.bilibili.com/bapis/main.community.interface.emote.EmoteService/AllPackages'
            ts = int(time.time())

            params = {
                'access_key': self.ACCESS_KEY,
                'build': 8230800,
                'business': 'reply',
                'channel': 'master',
                'disable_rcmd': 0,
                'mobi_app': 'android_i',
                'platform': 'android',
                'pn': 1,
                'ps': 100,
                'search': '',
                'statistics': '{"appId":14,"platform":3,"version":"3.20.4","abtest":""}',
                'ts': ts
            }

            headers = {
                'native_api_from': 'h5',
                'cookie': self.COOKIE,
                'accept': 'application/json, text/plain, */*',
                'referer': 'https://www.bilibili.com/h5/mall/emoji-package/more?navhide=1&native.theme=0',
                'content-type': 'application/json',
                'user-agent': (
                    'Mozilla/5.0 (Linux; Android 13; Mi 10 Build/TKQ1.221114.001; wv) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/135.0.7049.111 '
                    'Mobile Safari/537.36 os/android model/Mi 10 build/8230800 osVer/13 sdkInt/33 '
                    'network/2 BiliApp/8230800 mobi_app/android_i channel/master innerVer/8230800 '
                    'c_locale/zh_CN s_locale/zh_CN disable_rcmd/0 themeId/0 sh/33 3.20.4'
                ),
                'bili-http-engine': 'cronet',
                'accept-encoding': 'gzip, deflate, br'
            }

            signed_params = appsign(params, 'bb3101000e232e27', '36efcfed79309338ced0380abd824ac1')
            res1 = requests.get(base_url, params=signed_params, headers=headers, proxies=self.PROXY).json()

            if res1.get('code') != 0:
                print(f"[ERROR] 初次请求失败: {res1.get('message')}")
                return self.SCAN_CONFIG['end']

            total = res1.get('data', {}).get('total', 0)
            params['pn'] = total // 100 + 1
            params['ts'] = int(time.time())  # 更新时间戳
            signed_params = appsign(params, 'bb3101000e232e27', '36efcfed79309338ced0380abd824ac1')
            res = requests.get(base_url, params=signed_params, headers=headers, proxies=self.PROXY).json()

            if res.get('code') == 0 and 'packages' in res['data']:
                return max(*(pkg['id'] for pkg in res['data']['packages']), *(pkg['id'] for pkg in res1['data']['packages']))
            else:
                print(f"[ERROR] 获取最后一页失败: {res.get('message')}")
                return self.SCAN_CONFIG['end']

        except Exception as e:
            print(f"[ERROR] 获取最新表情包ID异常: {e}")
            return self.SCAN_CONFIG['end']

    def get_thread_session(self):
        if not hasattr(self.local, 'session'):
            self.local.session = requests.Session()
        return self.local.session

    def _worker(self, id):
        session = self.get_thread_session()  # 每个线程使用自己的 session
        emoji_info = self.get_emoji_info(id, session)
        if emoji_info:
            self.save_emoji_info(emoji_info)

    def main(self):
        """
        主函数，使用多线程并发获取表情包信息并保存
        """
        end_id = self.get_latest_emoji_id()
        ids = list(range(self.SCAN_CONFIG['start'], end_id + 50))
        ignore_ids = self.SCAN_CONFIG['ignore']
        ids = [id_ for id_ in ids if id_ not in ignore_ids]

        max_workers = 20  # 线程数
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self._worker, id_) for id_ in ids]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"[ERROR] 线程任务失败: {e}")


if __name__ == "__main__":
    BiliEmoji = BiliEmoji()
    BiliEmoji.main()  # 主函数调用
