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


def _protobuf_to_dict(data: bytes) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    index = 0
    while index < len(data):
        key, index = _read_varint(data, index)
        field_number = key >> 3
        wire_type = key & 0x07
        field_key = str(field_number)

        if wire_type == 0:
            value, index = _read_varint(data, index)
            _merge_field(fields, field_key, value)
        elif wire_type == 1:
            value = struct.unpack('<Q', data[index:index + 8])[0]
            index += 8
            _merge_field(fields, field_key, value)
        elif wire_type == 2:
            length, index = _read_varint(data, index)
            raw = data[index:index + length]
            index += length
            if _is_printable_utf8(raw):
                value: PbValue = raw.decode('utf-8')
            else:
                value = _protobuf_to_dict(raw)
            _merge_field(fields, field_key, value)
        elif wire_type == 5:
            value = struct.unpack('<I', data[index:index + 4])[0]
            index += 4
            _merge_field(fields, field_key, value)
        else:
            raise ValueError(f'unsupported protobuf wire type: {wire_type}')
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
