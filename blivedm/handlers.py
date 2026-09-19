# -*- coding: utf-8 -*-
import asyncio
import os
import time
import json
import logging
from pathlib import Path
from typing import *

import aiohttp

from .clients import ws_base
from .models import web as web_models, open_live as open_models

__all__ = (
    'HandlerInterface',
    'BaseHandler',
    'RoomHandler',
)

logger = logging.getLogger('blivedm')

_UNKNOWN_CMDS_CACHE_FILE = Path(os.environ.get(
    'BLIVEDM_UNKNOWN_CMDS_FILE',
    Path.home() / '.cache' / 'blivedm' / 'unknown_cmds.json',
))

_DEFAULT_UNKNOWN_CMDS = {
    "ANCHOR_LOT_AWARD",
    "ANCHOR_LOT_CHECKSTATUS",
    "ANCHOR_LOT_END",
    "ANCHOR_LOT_NOTICE",
    "ANCHOR_LOT_START",
    "CHG_RANK_REFRESH",
    "COMBO_SEND",
    "COMMON_ANIMATION",
    "COMMON_NOTICE_DANMAKU",
    "CUSTOM_NOTICE_CARD",
    "DANMU_ACTIVITY_CONFIG",
    "DANMU_AGGREGATION",
    "DM_INTERACTION",
    "ENTRY_EFFECT",
    "FLOW_REWARD_CARD",
    "FULL_SCREEN_SPECIAL_EFFECT",
    "GIFT_COMBO",
    "GIFT_PANEL_PLAN",
    "GOTO_BUY_FLOW",
    "GUARD_ACHIEVEMENT_ROOM",
    "GUARD_HONOR_THOUSAND",
    "HOT_BUY_NUM",
    "HOT_RANK_CHANGED",
    "HOT_RANK_CHANGED_V2",
    "HOT_ROOM_NOTIFY",
    "INTERACTIVE_USER",
    "INTERACT_WORD",
    "LIKE_GUIDE_USER",
    "LIKE_INFO_V3_CLICK",
    "LIKE_INFO_V3_UPDATE",
    "LIVE_ANI_RES_UPDATE",
    "LIVE_INTERACTIVE_GAME",
    "LIVE_INTERACT_GAME_STATE_CHANGE",
    "LIVE_MULTI_VIEW_NEW_INFO",
    "LIVE_OPEN_PLATFORM_GAME",
    "LIVE_PANEL_CHANGE_CONTENT",
    "LIVE_ROOM_TOAST_MESSAGE",
    "LOG_IN_NOTICE",
    "NOTICE_MSG",
    "ONLINE_RANK_TOP3",
    "ONLINE_RANK_V2",
    "ONLINE_RANK_V3",
    "OPENPLATFORM_GAME_BUTTON_STATUS_CHANGE",
    "OTHER_SLICE_LOADING_RESULT",
    "PANEL_INTERACTIVE_NOTIFY_CHANGE",
    "PK_BATTLE_END",
    "PK_BATTLE_ENTRANCE",
    "PK_BATTLE_FINAL_PROCESS",
    "PK_BATTLE_PRE",
    "PK_BATTLE_PRE_NEW",
    "PK_BATTLE_PROCESS",
    "PK_BATTLE_PROCESS_NEW",
    "PK_BATTLE_PUNISH_END",
    "PK_BATTLE_SETTLE",
    "PK_BATTLE_SETTLE_NEW",
    "PK_BATTLE_SETTLE_USER",
    "PK_BATTLE_SETTLE_V2",
    "PK_BATTLE_START",
    "PK_BATTLE_START_NEW",
    "PK_INFO",
    "PK_WIDGET",
    "PLAYURL_RELOAD",
    "PLAYURL_RELOAD_MASTER",
    "POPULARITY_RANK_TAB_CHG",
    "POPULARITY_RED_POCKET_NEW",
    "POPULARITY_RED_POCKET_START",
    "POPULARITY_RED_POCKET_V2_NEW",
    "POPULARITY_RED_POCKET_V2_START",
    "POPULARITY_RED_POCKET_V2_WINNER_LIST",
    "POPULARITY_RED_POCKET_WINNER_LIST",
    "POPULAR_RANK_CHANGED",
    "RANK_CHANGED",
    "RANK_CHANGED_V2",
    "RANK_REM",
    "RECALL_DANMU_MSG",
    "REVENUE_DISPLAY_EFFECT",
    "ROOM_CHANGE",
    "ROOM_REAL_TIME_MESSAGE_UPDATE",
    "ROOM_SILENT_ON",
    "ROOM_SKIN_MSG",
    "SHOPPING_CART_SHOW",
    "SHOPPING_EXPLAIN_CARD",
    "STOP_LIVE_ROOM_LIST",
    "SUPER_CHAT_ENTRANCE",
    "SUPER_CHAT_MESSAGE_JPN",
    "SYS_MSG",
    "TIP_CARD",
    "TRADING_SCORE",
    "UNIVERSAL_EVENT_GIFT",
    "UNIVERSAL_EVENT_GIFT_V2",
    "USER_TOAST_MSG",
    "VOICE_JOIN_LIST",
    "VOICE_JOIN_ROOM_COUNT_INFO",
    "WATCHED_CHANGE",
    "WEALTH_NOTIFY",
    "WIDGET_BANNER",
    "WIDGET_GIFT_STAR_PROCESS_V2",
    "WIDGET_WISH_INFO",
    "WIDGET_WISH_INFO_V2",
    "test"
}
"""内置的已知未知cmd，用于抑制重复告警"""


def _load_persisted_unknown_cmds() -> Set[str]:
    try:
        with _UNKNOWN_CMDS_CACHE_FILE.open('r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return {cmd for cmd in data if isinstance(cmd, str)}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return set()


def _persist_unknown_cmd(cmd: str):
    if cmd in _DEFAULT_UNKNOWN_CMDS:
        return

    persisted_cmds = _load_persisted_unknown_cmds()
    if cmd in persisted_cmds:
        return

    persisted_cmds.add(cmd)
    try:
        _UNKNOWN_CMDS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _UNKNOWN_CMDS_CACHE_FILE.open('w', encoding='utf-8') as f:
            json.dump(sorted(persisted_cmds), f, ensure_ascii=False, indent=2)
    except OSError:
        logger.warning('failed to persist unknown_cmd=%s to %s', cmd, _UNKNOWN_CMDS_CACHE_FILE)


logged_unknown_cmds = _DEFAULT_UNKNOWN_CMDS | _load_persisted_unknown_cmds()
"""已打日志的未知cmd（内置 + 本地缓存）"""


class HandlerInterface:
    """
    直播消息处理器接口
    """

    def handle(self, client: ws_base.WebSocketClientBase, command: dict):
        raise NotImplementedError

    def on_client_stopped(self, client: ws_base.WebSocketClientBase, exception: Optional[Exception]):
        """
        当客户端停止时调用。可以在这里close或者重新start
        """


def _make_msg_callback(method_name, message_cls):
    def callback(self: 'BaseHandler', client: ws_base.WebSocketClientBase, command: dict):
        method = getattr(self, method_name)
        return method(client, message_cls.from_command(command['data']))
    return callback


class BaseHandler(HandlerInterface):
    """
    一个简单的消息处理器实现，带消息分发和消息类型转换。继承并重写_on_xxx方法即可实现自己的处理器
    """

    def __danmu_msg_callback(self, client: ws_base.WebSocketClientBase, command: dict):
        return self._on_danmaku(client, web_models.DanmakuMessage.from_command(command['info']))

    def __danmu_msg_mirror_callback(self, client: ws_base.WebSocketClientBase, command: dict):
        message = web_models.DanmakuMessage.from_command(command['info'])
        message.is_mirror = True
        return self._on_danmaku(client, message)

    def __open_dm_mirror_callback(self, client: ws_base.WebSocketClientBase, command: dict):
        # 跨房弹幕可能缺少一些字段，详情参考官方文档
        message = open_models.DanmakuMessage.from_command(command['data'])
        message.is_mirror = True
        return self._on_open_live_danmaku(client, message)

    _CMD_CALLBACK_DICT: Dict[
        str,
        Optional[Callable[
            ['BaseHandler', ws_base.WebSocketClientBase, dict],
            Any
        ]]
    ]
    """cmd -> 处理回调"""
    _CMD_CALLBACK_DICT = {
        # 收到心跳包，这是blivedm自造的消息，原本的心跳包格式不一样
        '_HEARTBEAT': _make_msg_callback('_on_heartbeat', web_models.HeartbeatMessage),
        # 弹幕
        # go-common\app\service\live\live-dm\service\v1\send.go
        'DANMU_MSG': __danmu_msg_callback,
        'DANMU_MSG_MIRROR': __danmu_msg_mirror_callback,
        # 礼物（旧版 JSON 与 V2 protobuf 并存，GiftMessage.from_command 自动识别）
        'SEND_GIFT': _make_msg_callback('_on_gift', web_models.GiftMessage),
        'SEND_GIFT_V2': _make_msg_callback('_on_gift', web_models.GiftMessage),
        # 上舰
        'GUARD_BUY': _make_msg_callback('_on_buy_guard', web_models.GuardBuyMessage),
        # 另一个上舰消息
        'USER_TOAST_MSG_V2': _make_msg_callback('_on_user_toast_v2', web_models.UserToastV2Message),
        # 醒目留言
        'SUPER_CHAT_MESSAGE': _make_msg_callback('_on_super_chat', web_models.SuperChatMessage),
        # 删除醒目留言
        'SUPER_CHAT_MESSAGE_DELETE': _make_msg_callback('_on_super_chat_delete', web_models.SuperChatDeleteMessage),
        # 进入房间、关注主播等互动消息
        'INTERACT_WORD_V2': _make_msg_callback('_on_interact_word_v2', web_models.InteractWordV2Message),
        # 高能榜 / 直播间观看人数（持续下发，RoomHandler 按间隔挂到普通弹幕上）
        'ONLINE_RANK_COUNT': _make_msg_callback('_on_online_rank_count', web_models.OnlineRankCountMessage),
        # 开播 / 下播（web 端房间事件，payload 不稳定，把原始 command 交给上层）
        'LIVE': lambda self, client, command: self._on_live(client, command),
        'PREPARING': lambda self, client, command: self._on_preparing(client, command),

        #
        # 开放平台消息
        #

        # 弹幕
        'LIVE_OPEN_PLATFORM_DM': _make_msg_callback('_on_open_live_danmaku', open_models.DanmakuMessage),
        'LIVE_OPEN_PLATFORM_DM_MIRROR': __open_dm_mirror_callback,
        # 礼物
        'LIVE_OPEN_PLATFORM_SEND_GIFT': _make_msg_callback('_on_open_live_gift', open_models.GiftMessage),
        # 上舰
        'LIVE_OPEN_PLATFORM_GUARD': _make_msg_callback('_on_open_live_buy_guard', open_models.GuardBuyMessage),
        # 醒目留言
        'LIVE_OPEN_PLATFORM_SUPER_CHAT': _make_msg_callback('_on_open_live_super_chat', open_models.SuperChatMessage),
        # 删除醒目留言
        'LIVE_OPEN_PLATFORM_SUPER_CHAT_DEL': _make_msg_callback(
            '_on_open_live_super_chat_delete', open_models.SuperChatDeleteMessage
        ),
        # 点赞
        'LIVE_OPEN_PLATFORM_LIKE': _make_msg_callback('_on_open_live_like', open_models.LikeMessage),
        # 进入房间
        'LIVE_OPEN_PLATFORM_LIVE_ROOM_ENTER': _make_msg_callback('_on_open_live_enter_room', open_models.RoomEnterMessage),
        # 开始直播
        'LIVE_OPEN_PLATFORM_LIVE_START': _make_msg_callback('_on_open_live_start_live', open_models.LiveStartMessage),
        # 结束直播
        'LIVE_OPEN_PLATFORM_LIVE_END': _make_msg_callback('_on_open_live_end_live', open_models.LiveEndMessage),
    }

    def handle(self, client: ws_base.WebSocketClientBase, command: dict):
        cmd = command.get('cmd', '')
        pos = cmd.find(':')  # 2019-5-29 B站弹幕升级新增了参数
        if pos != -1:
            cmd = cmd[:pos]

        if cmd not in self._CMD_CALLBACK_DICT:
            # 只有第一次遇到未知cmd时打日志
            if cmd not in logged_unknown_cmds:
                # logger.warning('room=%d, unknown_cmd=%s, command=%s', client.room_id, cmd, command)
                logged_unknown_cmds.add(cmd)
                _persist_unknown_cmd(cmd)
            return

        callback = self._CMD_CALLBACK_DICT[cmd]
        if callback is not None:
            callback(self, client, command)

    def _on_heartbeat(self, client: ws_base.WebSocketClientBase, message: web_models.HeartbeatMessage):
        """收到心跳包"""

    def _on_danmaku(self, client: ws_base.WebSocketClientBase, message: web_models.DanmakuMessage):
        """弹幕"""

    def _on_gift(self, client: ws_base.WebSocketClientBase, message: web_models.GiftMessage):
        """礼物"""

    def _on_buy_guard(self, client: ws_base.WebSocketClientBase, message: web_models.GuardBuyMessage):
        """上舰"""

    def _on_user_toast_v2(self, client: ws_base.WebSocketClientBase, message: web_models.UserToastV2Message):
        """另一个上舰消息"""

    def _on_super_chat(self, client: ws_base.WebSocketClientBase, message: web_models.SuperChatMessage):
        """醒目留言"""

    def _on_super_chat_delete(self, client: ws_base.WebSocketClientBase, message: web_models.SuperChatDeleteMessage):
        """删除醒目留言"""

    def _on_interact_word_v2(self, client: ws_base.WebSocketClientBase, message: web_models.InteractWordV2Message):
        """进入房间、关注主播等互动消息"""

    def _on_online_rank_count(self, client: ws_base.WebSocketClientBase, message: web_models.OnlineRankCountMessage):
        """高能榜 / 直播间观看人数"""

    def _on_live(self, client: ws_base.WebSocketClientBase, command: dict):
        """直播间开播"""

    def _on_preparing(self, client: ws_base.WebSocketClientBase, command: dict):
        """直播间下播 / 准备中"""

    #
    # 开放平台消息
    #

    def _on_open_live_danmaku(self, client: ws_base.WebSocketClientBase, message: open_models.DanmakuMessage):
        """弹幕"""

    def _on_open_live_gift(self, client: ws_base.WebSocketClientBase, message: open_models.GiftMessage):
        """礼物"""

    def _on_open_live_buy_guard(self, client: ws_base.WebSocketClientBase, message: open_models.GuardBuyMessage):
        """上舰"""

    def _on_open_live_super_chat(self, client: ws_base.WebSocketClientBase, message: open_models.SuperChatMessage):
        """醒目留言"""

    def _on_open_live_super_chat_delete(
        self, client: ws_base.WebSocketClientBase, message: open_models.SuperChatDeleteMessage
    ):
        """删除醒目留言"""

    def _on_open_live_like(self, client: ws_base.WebSocketClientBase, message: open_models.LikeMessage):
        """点赞"""

    def _on_open_live_enter_room(self, client: ws_base.WebSocketClientBase, message: open_models.RoomEnterMessage):
        """进入房间"""

    def _on_open_live_start_live(self, client: ws_base.WebSocketClientBase, message: open_models.LiveStartMessage):
        """开始直播"""

    def _on_open_live_end_live(self, client: ws_base.WebSocketClientBase, message: open_models.LiveEndMessage):
        """结束直播"""


class RoomHandler(BaseHandler):
    """
    功能丰富的直播间弹幕处理器，支持弹幕统计、彩色输出和打印延迟
    """

    _HISTORY_URL = 'https://api.live.bilibili.com/xlive/web-room/v1/dM/gethistory'

    # 颜色转义序列
    gray   = "\033[37m"
    cyan   = "\033[36m"
    purple = "\033[35m"
    blue   = "\033[34m"
    yellow = "\033[33m"
    green  = "\033[32m"
    red    = "\033[31m"
    white  = "\033[0m"

    def __init__(self, show_entering=False):
        self.count: Dict[Hashable, int] = {}  # 发言者标识 -> 出现次数
        self.last_print_time = 0  # 上次打印时间
        self.print_time_interval = 0.1  # 相邻弹幕的打印间隔时间
        self.show_entering = show_entering
        self.online_count: Optional[int] = None  # 最新直播间观看人数
        self.last_online_count_print_time = 0.0  # 上次把人数挂到弹幕上的时间
        self.online_count_print_interval = 300  # 人数展示间隔（秒）

    def _print_with_delay(self):
        """带延迟的打印"""
        current_time = time.time()
        time_since_last_print = current_time - self.last_print_time
        if time_since_last_print < self.print_time_interval:
            time.sleep(max(0, self.print_time_interval - time_since_last_print))
        self.last_print_time = time.time()

    def _format_danmaku_text(self, msg: str) -> str:
        msg = msg.replace('\n', ' ')
        if msg.startswith("点歌 "):
            return f"{self.gray}{msg}{self.white}"
        return f"{self.white}{msg}"

    def _consume_online_count_suffix(self) -> str:
        """若已到展示间隔，返回人数后缀并刷新计时；否则返回空字符串。"""
        if self.online_count is None:
            return ''
        now = time.time()
        if self.last_online_count_print_time and now - self.last_online_count_print_time < self.online_count_print_interval:
            return ''
        self.last_online_count_print_time = now
        return f" {self.gray}({self.online_count} online){self.white}"

    def _speaker_key(self, uid: int = 0, uname: str = '', uid_crc32: str = '') -> Hashable:
        """未登录时服务端会把 uid 置 0，改用 crc32 / 用户名区分发言者。"""
        if uid:
            return uid
        if uid_crc32:
            return f"crc:{uid_crc32}"
        return uname or 0

    def _print_danmaku(self, timeline: str, level, uid: int, uname: str, text: str, suffix: str = '', uid_crc32: str = ''):
        key = self._speaker_key(uid, uname, uid_crc32)
        self.count[key] = self.count.get(key, 0) + 1
        self._print_with_delay()
        print(f"{self.gray}{timeline} {self.cyan}{level:>2} {uname}{self.green}|{self.count[key]}〉{text}{suffix}")

    async def load_history(self, session: aiohttp.ClientSession, room_id: int):
        """拉取并打印进房前的历史弹幕，与实时弹幕共用 uid 计数和打印延迟"""
        try:
            async with session.get(
                self._HISTORY_URL,
                params={'roomid': room_id},
                headers={
                    'Referer': 'https://live.bilibili.com',
                    'User-Agent': (
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                        '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
                    ),
                },
            ) as response:
                response.raise_for_status()
                payload = await response.json()
        except (aiohttp.ClientError, asyncio.CancelledError):
            raise
        except Exception as e:
            logger.warning('failed to load danmaku history for room=%d: %s', room_id, e)
            return

        posts = sorted(payload.get('data', {}).get('room', []), key=lambda x: x.get('timeline', ''))
        for post in posts:
            if post.get('dm_type', 0) != 0:
                continue
            timeline = post.get('timeline', '').split(' ')[-1]
            medal = post.get('medal') or []
            level = 'GM' if post.get('isadmin') else medal[0] if medal else ''
            uid = post.get('uid', 0)
            uname = post.get('nickname', '')
            text = self._format_danmaku_text(post.get('text', ''))
            self._print_danmaku(timeline, level, uid, uname, text)

    def _on_heartbeat(self, client: ws_base.WebSocketClientBase, message: web_models.HeartbeatMessage):
        # 心跳消息可以不打印，避免刷屏
        pass

    def _on_interact_word_v2(self, client: ws_base.WebSocketClientBase, message: web_models.InteractWordV2Message):
        """进入房间、关注主播等互动消息"""
        timeline = time.strftime("%H:%M:%S", time.localtime(message.timestamp))
        uname = message.username
        uid = message.uid
        if self.show_entering:
            print(f"{self.gray}{timeline} ⮑  {uname}{self.white}")

    def _on_online_rank_count(self, client: ws_base.WebSocketClientBase, message: web_models.OnlineRankCountMessage):
        """缓存最新观看人数，不单独打印"""
        self.online_count = message.online_count

    def _on_danmaku(self, client: ws_base.WebSocketClientBase, message: web_models.DanmakuMessage):
        """普通弹幕"""
        if message.dm_type == 0:
            timeline = time.strftime("%H:%M:%S", time.localtime(message.timestamp / 1000))
            level = "GM" if message.admin else message.medal_level if message.medal_level else ''
            text = self._format_danmaku_text(message.msg)
            suffix = self._consume_online_count_suffix()
            self._print_danmaku(
                timeline, level, message.uid, message.uname, text, suffix,
                uid_crc32=message.uid_crc32,
            )

    def _on_super_chat(self, client: ws_base.WebSocketClientBase, message: web_models.SuperChatMessage):
        """SC弹幕"""
        timeline = time.strftime("%H:%M:%S", time.localtime(message.start_time))
        level = message.medal_level if message.medal_level else ''
        uid = message.uid
        uname = message.uname
        text = message.message
        price = message.price
        key = self._speaker_key(uid, uname)
        self.count[key] = self.count.get(key, 0) + 1
        self._print_with_delay()
        print(f"{self.gray}{timeline} {self.cyan}{level:>2} {uname}{self.green}|{self.count[key]}〉{self.white}{text} {self.red}￥{price}{self.white}")

    def _on_gift(self, client: ws_base.WebSocketClientBase, message: web_models.GiftMessage):
        """礼物"""
        timeline = time.strftime("%H:%M:%S", time.localtime(message.timestamp))
        level = message.medal_level if message.medal_level else ''
        uid = message.uid
        uname = message.uname
        text = f"{message.gift_name} ×{message.num}"
        price = message.price / 1000 * message.num
        key = self._speaker_key(uid, uname)
        self.count[key] = self.count.get(key, 0) + 1
        self._print_with_delay()
        print(f"{self.gray}{timeline} {self.cyan}{level:>2} {uname}{self.green}|{self.count[key]}〉{self.gray}{text} {self.red}￥{price:.1f}{self.white}")

    def _on_user_toast_v2(self, client: ws_base.WebSocketClientBase, message: web_models.UserToastV2Message):
        """上舰"""
        if message.source != 2:
            import re
            timeline = time.strftime("%H:%M:%S", time.localtime(message.start_time))
            level = message.guard_level if message.guard_level else ''
            uid = message.uid
            uname = message.username
            text = f"{re.search(r'(舰长|提督|总督)', message.toast_msg).group()} ×{message.num}{message.unit}"
            price = message.price / 1000
            key = self._speaker_key(uid, uname)
            self.count[key] = self.count.get(key, 0) + 1
            self._print_with_delay()
            print(f"{self.gray}{timeline} {self.purple}{level:>2} {self.cyan}{uname}{self.green}|{self.count[key]}〉{self.white}{text} {self.red}￥{price}{self.white}")
