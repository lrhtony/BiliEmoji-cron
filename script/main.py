# -*- coding: UTF-8 -*-
import requests
import json
import time
import os

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

    def get_emoji_info(self, ids: list) -> list:
        """
        根据表情包ID列表获取表情包信息
        :param ids: 表情包ID列表
        :return: 表情包信息列表
        """
        params = {
            'business': 'reply',
            'ids': ','.join([str(i) for i in ids]),
            'mobi_app': 'android_i'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
            'Referer': 'https://www.bilibili.com/',
            'Origin': 'https://www.bilibili.com',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.9'
        }
        # 发送请求获取表情包信息
        response = requests.get('https://api.bilibili.com/x/emote/package', params=params, proxies=self.PROXY, headers=headers)
        response_json = response.json()
        if response_json['code'] != 0:  # 检查返回结果是否正常
            raise Exception(response_json['message'])

        result = []
        packages = response_json['data']['packages']
        if packages:
            for package in packages:
                package_dict = self._parse_package(package)  # 解析表情包信息
                result.append(package_dict)
        return result

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
            'resource_type': package['resource_type'],
        }
        if 'emote' in package:
            emote_list = []
            for emote in package['emote']:
                emote_data = {
                    'text': emote['text'].replace('[', '').replace(']', ''),
                    'url': emote['url'].replace('http://', 'https://'),
                }
                if 'gif_url' in emote:  # 动态表情
                    emote_data['gif_url'] = emote['gif_url'].replace('http://', 'https://')
                if 'webp_url' in emote:
                    emote_data['webp_url'] = emote['webp_url'].replace('http://', 'https://')
                emote_list.append(emote_data)
            package_dict['emote'] = emote_list
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
        :return: 最新表情包ID
        """
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
            'ts': int(time.time())
        }
        headers = {
            'native_api_from': 'h5',
            'cookie': self.COOKIE,
            'accept': 'application/json, text/plain, */*',
            'referer': 'https://www.bilibili.com/h5/mall/emoji-package/more?navhide=1&native.theme=0',
            'content-type': 'application/json',
            'user-agent': 'Mozilla/5.0 (Linux; Android 13; Mi 10 Build/TKQ1.221114.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/135.0.7049.111 Mobile Safari/537.36 os/android model/Mi 10 build/8230800 osVer/13 sdkInt/33 network/2 BiliApp/8230800 mobi_app/android_i channel/master innerVer/8230800 c_locale/zh_CN s_locale/zh_CN disable_rcmd/0 themeId/0 sh/33 3.20.4 os/android model/Mi 10 mobi_app/android_i build/8230800 channel/master innerVer/8230800 osVer/13 network/2',
            'bili-http-engine': 'cronet',
            'accept-encoding': 'gzip, deflate, br'
        }
        sign_params = appsign(params, 'bb3101000e232e27', '36efcfed79309338ced0380abd824ac1')
        response = requests.get(
            'https://api.bilibili.com/bapis/main.community.interface.emote.EmoteService/AllPackages',
            params=sign_params, proxies=self.PROXY, headers=headers)
        res = response.json()
        if res['code'] != 0:
            # 警告并返回SCAN_CONFIG['end']
            print(f"[WARN] 获取最新表情包id失败: {res['message']}")
            return self.SCAN_CONFIG['end']
        # 遍历所有表情包，获取最新的表情包id
        return max(package['id'] for package in res['data']['packages'])

    def main(self):
        """
        主函数，获取表情包信息并保存
        """
        end_id = self.get_latest_emoji_id()
        ids = list(range(self.SCAN_CONFIG['start'], end_id + 50))  # 获取表情包id列表
        ignore_ids = self.SCAN_CONFIG['ignore']  # 需要忽略的id
        ids = [id_ for id_ in ids if id_ not in ignore_ids]  # 删除不必要的id
        for i in range(0, len(ids), self.SCAN_CONFIG['step']):  # 分批获取表情包信息
            id_list = ids[i:i + self.SCAN_CONFIG['step']]
            emojis_info = self.get_emoji_info(id_list)  # 批量获取表情包信息
            for emoji_info in emojis_info:
                self.save_emoji_info(emoji_info)  # 逐个保存表情包信息


if __name__ == "__main__":
    BiliEmoji = BiliEmoji()
    BiliEmoji.main()  # 主函数调用
