# -*- coding: utf-8 -*-
import argparse
import asyncio
import http.cookies
import sys
import time
from typing import *

import aiohttp

import blivedm
import blivedm.models.web as web_models

# 颜色转义序列
gray   = "\033[37m"
cyan   = "\033[36m"
purple = "\033[35m"
blue   = "\033[34m"
yellow = "\033[33m"
green  = "\033[32m"
red	   = "\033[31m"
white  = "\033[0m"

session: Optional[aiohttp.ClientSession] = None


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='持续监听 Bilibili 直播间弹幕',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''示例:
  python listen_room.py 12235923
  python listen_room.py 12235923 --sessdata "your_sessdata_here"
'''
    )
    parser.add_argument(
        'room_id',
        type=int,
        help='直播间ID（从直播间URL获取，例如 https://live.bilibili.com/12235923 中的 12235923）'
    )
    parser.add_argument(
        '--sessdata',
        type=str,
        default='',
        help='可选：已登录账号的 SESSDATA 值（不填则用户名会打码）'
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    init_session(args.sessdata)
    try:
        await listen_room(args.room_id)
    finally:
        if session:
            await session.close()


def init_session(sessdata: str):
    cookies = http.cookies.SimpleCookie()
    cookies['SESSDATA'] = sessdata
    cookies['SESSDATA']['domain'] = 'bilibili.com'

    global session
    session = aiohttp.ClientSession()
    session.cookie_jar.update_cookies(cookies)


async def listen_room(room_id: int):
    """持续监听指定直播间"""
    client = blivedm.BLiveClient(room_id, session=session)
    handler = RoomHandler()
    client.set_handler(handler)

    print(f'开始监听直播间: {room_id}')
    print('按 Ctrl+C 停止监听...')

    client.start()
    try:
        # 持续运行直到被中断
        await client.join()
    except KeyboardInterrupt:
        print('\n正在停止监听...')
        client.stop()
        await client.join()
    finally:
        await client.stop_and_close()
        print('监听已停止')


class RoomHandler(blivedm.BaseHandler):
    def __init__(self):
        self.count: Dict[int, int] = {}  # uid -> 出现次数

    def _on_heartbeat(self, client: blivedm.BLiveClient, message: web_models.HeartbeatMessage):
        # 心跳消息可以不打印，避免刷屏
        pass

    def _on_danmaku(self, client: blivedm.BLiveClient, message: web_models.DanmakuMessage):
        timeline = time.strftime("%H:%M:%S", time.localtime(message.timestamp / 1000))
        level = '〄' if message.admin else message.medal_level if message.medal_level else ''
        uid = message.uid_crc32
        uname = message.uname
        text = message.msg
        self.count[uid] = self.count.get(uid, 0) + 1 # 统计 uid 出现次数
        print(f"{gray}{timeline} {cyan}{level:>2} {uname}{green}|{self.count[uid]}〉{white}{text}")
        # print(f'[{client.room_id}] {message.uname}：{message.msg}')

    def _on_gift(self, client: blivedm.BLiveClient, message: web_models.GiftMessage):
        timeline = time.strftime("%H:%M:%S", time.localtime(message.timestamp))
        level = message.medal_level if message.medal_level else ''
        uid = message.uid
        uname = message.uname
        text = f"{message.gift_name} ×{message.num}"
        price = message.price / 1000
        self.count[uid] = self.count.get(uid, 0) + 1  # 统计 uid 出现次数
        print(f"{gray}{timeline} {cyan}{level:>2} {uname}{green}|{self.count[uid]}〉{white}{text} {red}￥{price:.1f}{white}")
        # print(f'[{client.room_id}] {message.uname} 赠送{message.gift_name}x{message.num} （{message.coin_type}瓜子x{message.total_coin}）')

    def _on_user_toast_v2(self, client: blivedm.BLiveClient, message: web_models.UserToastV2Message):
        if message.source != 2:
            import re
            timeline = time.strftime("%H:%M:%S", time.localtime(message.start_time))
            level = message.guard_level if message.guard_level else ''
            uid = message.uid
            uname = message.username
            text = f"{re.search(r'(舰长|提督|总督)', text).group()} ×{message.num}{message.unit}"
            price = message.price / 1000
            print(f"{gray}{timeline} {purple}{level:>2} {cyan}{uname}{green}|{self.count[uid]}〉{white}{text} {red}￥{price}{white}")
            # print(f'[{client.room_id}] {message.username} 上舰，guard_level={message.guard_level}')

    def _on_super_chat(self, client: blivedm.BLiveClient, message: web_models.SuperChatMessage):
        timeline = time.strftime("%H:%M:%S", time.localtime(message.start_time))
        level = message.medal_level if message.medal_level else ''
        uid = message.uid
        uname = message.uname
        text = message.message
        price = message.price
        self.count[uid] = self.count.get(uid, 0) + 1  # 统计 uid 出现次数
        print(f"{gray}{timeline} {cyan}{level:>2} {uname}{green}|{self.count[uid]}〉{white}{text} {red}￥{price}{white}")
        # print(f'[{client.room_id}] 醒目留言 ¥{message.price} {message.uname}：{message.message}')

    '''
    def _on_interact_word_v2(self, client: blivedm.BLiveClient, message: web_models.InteractWordV2Message):
        if message.msg_type == 1:
            print(f'[{client.room_id}] {message.username} 进入房间')
    '''


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n程序已退出')
