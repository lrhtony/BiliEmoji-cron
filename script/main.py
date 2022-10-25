# -*- coding: UTF-8 -*-
import requests
import redis
import json
import os


class BiliEmoji:
    def __init__(self):
        self.PROXY = json.loads(os.getenv('PROXY', '{}'))
        self.REDIS_URL = os.getenv('REDIS_URL')
        self.SCAN_CONFIG = json.loads(os.getenv('SCAN_CONFIG', '[]'))
        # self.PROXY = {'http': 'http://127.0.0.1:6667', 'https': 'http://127.0.0.1:6667'}
        # self.REDIS_URL = ''
        # self.SCAN_CONFIG = [1, 550, 20, [4, 250]]  # [初始值, 结束值, 步长, 忽略值]
        self.BILI_ACCESS_TOKEN = self.get_bili_access_token()

    def main(self):
        ids = list(range(self.SCAN_CONFIG[0], self.SCAN_CONFIG[1]))
        ignore_ids = self.SCAN_CONFIG[3]
        for ignore_id in ignore_ids:  # 删除一些不必要的id
            try:
                ids.remove(ignore_id)
            except ValueError:
                pass
        for i in range(0, len(ids), self.SCAN_CONFIG[2]):
            id_list = ids[i:i + self.SCAN_CONFIG[2]]
            emojis_info = self.get_emoji_info(id_list)  # 批量获取表情包信息
            for emoji_info in emojis_info:
                self.save_emoji_info(emoji_info)  # 逐个保存表情包信息

    def get_bili_access_token(self):
        r = redis.from_url(self.REDIS_URL)
        bili_access_token = str(r.hget('token', 'bili-access_key'), 'utf-8')
        return bili_access_token

    def get_emoji_info(self, ids: list) -> list:
        params = {
            'access_key': self.BILI_ACCESS_TOKEN,
            'business': 'reply',
            'ids': ','.join([str(i) for i in ids])
        }
        response = requests.get('https://api.bilibili.com/x/emote/package', params=params, proxies=self.PROXY)
        response_json = response.json()
        if response_json['code'] != 0:  # 乱七八糟的情况
            raise Exception(response_json['message'])

        result = []
        packages = response_json['data']['packages']
        if packages:
            for package in packages:
                package_id = package['id']
                package_text = package['text']
                package_icon = package['url'].replace('http://', 'https://')
                package_dict = {
                    'id': package_id,
                    'text': package_text,
                    'icon': package_icon,
                }
                if 'emote' in package:
                    emote_list = []
                    emotes = package['emote']
                    for emote in emotes:
                        emote_text = emote['text'].replace('[', '').replace(']', '')
                        emote_url = emote['url'].replace('http://', 'https://')
                        emote_list.append({
                            'text': emote_text,
                            'url': emote_url,
                        })
                    package_dict['emote'] = emote_list
                result.append(package_dict)
        return result

    @staticmethod
    def save_emoji_info(emoji_info: dict):
        emoji_id = emoji_info['id']
        emoji_text = emoji_info['text']
        filename = f'{emoji_id}-{emoji_text}.json'
        filepath = os.path.join('list', filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(json.dumps(emoji_info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    BiliEmoji = BiliEmoji()
    BiliEmoji.main()
