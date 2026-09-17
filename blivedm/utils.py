# -*- coding: utf-8 -*-
import base64
import struct
from typing import Any, Dict, List, Tuple, Union

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
)

PbValue = Union[int, float, str, Dict[str, Any], List[Any]]


def decode_pb_data(pb_data: str) -> Dict[str, Any]:
    """
    将 Base64 编码的 protobuf 二进制数据解码为 JSON 兼容的 dict。

    字段号作为字符串 key；重复字段会合并为 list。
    空的 length-delimited 字段会解码为 ''（空字符串），调用方读取嵌套对象时应使用 as_pb_dict()。
    """
    if not pb_data:
        return {}
    return _protobuf_to_dict(base64.b64decode(pb_data))


def as_pb_dict(value: Any) -> Dict[str, Any]:
    """将 decode_pb_data 的嵌套字段安全转为 dict。空字符串、None、list 等均视为 {}。"""
    return value if isinstance(value, dict) else {}


def _read_varint(data: bytes, index: int) -> Tuple[int, int]:
    result = 0
    shift = 0
    while index < len(data):
        byte = data[index]
        index += 1
        result |= (byte & 0x7f) << shift
        if not (byte & 0x80):
            return result, index
        shift += 7
    raise ValueError('invalid varint')


def _is_printable_utf8(raw: bytes) -> bool:
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        return False
    return all(char.isprintable() or char in '\n\r\t' for char in text)


def _merge_field(fields: Dict[str, Any], key: str, value: PbValue):
    if key not in fields:
        fields[key] = value
        return
    existing = fields[key]
    if isinstance(existing, list):
        existing.append(value)
    else:
        fields[key] = [existing, value]


def _decode_length_delimited(raw: bytes) -> PbValue:
    """length-delimited：可打印 UTF-8 当字符串；否则尝试嵌套 protobuf；失败则丢弃二进制。"""
    if _is_printable_utf8(raw):
        return raw.decode('utf-8')
    if not raw:
        return ''
    try:
        return _protobuf_to_dict(raw)
    except (ValueError, struct.error):
        return {}


def _protobuf_to_dict(data: bytes) -> Dict[str, Any]:
    """
    无 schema 的尽力解码。SEND_GIFT_V2 等消息里常混有 packed / bytes 字段，
    不能当嵌套 protobuf 读；截断或非法 wire type 时停止当前层，保留已解析字段。
    """
    fields: Dict[str, Any] = {}
    index = 0
    data_len = len(data)
    while index < data_len:
        try:
            key, index = _read_varint(data, index)
            field_number = key >> 3
            wire_type = key & 0x07
            field_key = str(field_number)

            if wire_type == 0:
                value, index = _read_varint(data, index)
            elif wire_type == 1:
                if index + 8 > data_len:
                    break
                value = struct.unpack_from('<Q', data, index)[0]
                index += 8
            elif wire_type == 2:
                length, index = _read_varint(data, index)
                if index + length > data_len:
                    break
                raw = data[index:index + length]
                index += length
                value = _decode_length_delimited(raw)
            elif wire_type == 5:
                if index + 4 > data_len:
                    break
                value = struct.unpack_from('<I', data, index)[0]
                index += 4
            else:
                break
        except (ValueError, struct.error):
            break
        _merge_field(fields, field_key, value)
    return fields


def make_constant_retry_policy(interval: float):
    def get_interval(_retry_count: int, _total_retry_count: int):
        return interval
    return get_interval


def make_linear_retry_policy(start_interval: float, interval_step: float, max_interval: float):
    def get_interval(retry_count: int, _total_retry_count: int):
        return min(
            start_interval + (retry_count - 1) * interval_step,
            max_interval
        )
    return get_interval
