# -*- coding: UTF-8 -*-
import os
import time
import urllib.parse
import hashlib
from datetime import datetime
import pymongo
import requests
import certifi


def appsign(params, appkey, appsec):
    """
    对请求参数进行签名
    :param params: 请求参数字典
    :param appkey: 应用的 appkey
    :param appsec: 应用的 appsec
    :return: 带签名的请求参数字典
    """
    params.update({'appkey': appkey})
    params = dict(sorted(params.items()))  # 按 key 排序参数
    query = urllib.parse.urlencode(params)  # 序列化参数
    sign = hashlib.md5((query + appsec).encode()).hexdigest()  # 计算签名
    params.update({'sign': sign})
    return params


def concat_cookies(cookies):
    """
    将 cookie 列表拼接成字符串
    :param cookies: cookie 列表，每个元素是字典，包含 name 和 value
    :return: 拼接后的 cookie 字符串
    """
    return ';'.join(f"{cookie['name']}={cookie['value']}" for cookie in cookies)


class BilibiliAuth:
    """
    Bilibili 认证类，用于管理账号的 access_token 和 cookie
    """
    def __init__(self, db_uri=None):
        """
        初始化 BilibiliAuth 实例
        :param db_uri: 数据库连接 URI，默认为环境变量 ACCOUNT_DB_URI
        """
        self.MONGO_CLIENT = pymongo.MongoClient(
            db_uri or os.getenv('ACCOUNT_DB_URI', 'mongodb://localhost:27017/'),
            tlsCAFile=certifi.where()
        )

    def get_access(self, mid):
        """
        获取指定用户的 access_token 和 cookie
        :param mid: 用户的 mid
        :return: access_token 和 cookie 字符串
        """
        account_info = self.MONGO_CLIENT['bilibili']['accounts'].find_one({'mid': mid})
        access_key = account_info['token_info']['access_token']
        refresh_token = account_info['token_info']['refresh_token']
        cookie_info = account_info['cookie_info']['cookies']
        cookie_str = concat_cookies(cookie_info)
        last_update = account_info['last_update']

        # 如果距离上次更新时间超过 30 天，则重新获取 access_token
        if (datetime.now() - last_update).days > 30:
            access_key, cookie_str = self.refresh_access_token(access_key, refresh_token)
        return access_key, cookie_str

    def refresh_access_token(self, access_key, refresh_token):
        """
        刷新 access_token 并更新数据库
        :param access_key: 当前的 access_token
        :param refresh_token: 用于刷新 access_token 的 refresh_token
        :return: 新的 access_token 和 cookie 字符串
        """
        # 请求头
        headers = {
            'env': 'prod',
            'app-key': 'android_i',
            'user-agent': 'Mozilla/5.0 BiliDroid/3.20.4 (bbcallen@gmail.com) os/android model/Mi 10 mobi_app/android_i build/8230800 channel/master innerVer/8230800 osVer/13 network/2',
            'bili-http-engine': 'cronet',
            'content-type': 'application/x-www-form-urlencoded; charset=utf-8',
            'accept-encoding': 'gzip, deflate, br'
        }

        # 请求数据
        data = {
            'access_key': access_key,
            'build': '6750200',
            'c_locale': 'zh_CN',
            'channel': 'master',
            'device': 'phone',
            'disable_rcmd': '0',
            'from_access_key': access_key,
            'mobi_app': 'android_i',
            'platform': 'android',
            'refresh_token': refresh_token,
            's_locale': 'zh_CN',
            'statistics': '{"appId":14,"platform":3,"version":"3.20.4","abtest":""}',
            'sts': int(time.time()),
            'ts': int(time.time())
        }

        # 对数据进行签名
        data_sign = appsign(data, 'ae57252b0c09105d', 'c75875c596a69eb55bd119e74b07cfe3')

        # 发送请求刷新 token
        try:
            response = requests.post(
                'https://passport.bilibili.com/x/passport-login/oauth2/refresh_token',
                headers=headers,
                data=data_sign
            )
        except:
            raise Exception('Failed to request refresh token!')

        # 记录日志
        self.MONGO_CLIENT['bilibili']['logs'].insert_one({'date': datetime.now(), 'response': response.text})

        # 解析响应
        try:
            res = response.json()
        except ValueError:
            raise Exception('Failed to parse response!')
        if res['code'] == 0:
            # 更新数据库中的 token 和 cookie 信息
            self.MONGO_CLIENT['bilibili']['accounts'].update_one(
                {'mid': res['data']['token_info']['mid']},
                {
                    '$set': {
                        'token_info': res['data']['token_info'],
                        'cookie_info': res['data']['cookie_info'],
                        'last_update': datetime.now()
                    }
                }
            )
            access_key = res['data']['token_info']['access_token']
            cookie_info = res['data']['cookie_info']['cookies']
            cookie_str = concat_cookies(cookie_info)
            return access_key, cookie_str
        else:
            raise Exception('Refresh token failed!')


if __name__ == '__main__':
    # 示例用法
    auth = BilibiliAuth()
    access_token, cookie_str = auth.get_access(mid=1)
    # print(f"Access Token: {access_token}")
