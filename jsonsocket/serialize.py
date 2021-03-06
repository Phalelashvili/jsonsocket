import json
import struct
from base64 import b64encode, b64decode

try:
    import numpy as np
except ImportError:
    np = None

try:
    import pandas as pd
except ImportError:
    pd = None

complex_number_length = len(b64encode(struct.pack("ff", 0, 0)).decode("utf-8")) + 1
if np is not None:
    complex1 = np.array([1, 1j])


class BetterEncoder(json.JSONEncoder):
    def default(self, obj):
        if np is not None and isinstance(obj, np.ndarray):
            if "complex" in str(obj.dtype):
                shape = obj.shape
                values = obj.ravel()
                values = np.concatenate([np.real(values), np.imag(values)]).reshape((2, len(values))).T.ravel()
                encoded = b64encode(struct.pack("f" * len(values), *values)).decode("utf-8")
                res = dict(_decode_type="numpy_complex", _shape=shape, _content=encoded)
                return res
            return obj.tolist()
        if pd is not None and np is not None:
            typename = obj.__class__.__name__
            res = None
            if isinstance(obj, pd.DataFrame):
                content = dict(zip(obj.columns, obj.values.T.tolist()))
                for key, value in content.items():
                    unique = np.unique(value)
                    if len(unique) == 1:
                        content[key] = unique[0]
                res = dict(_decode_type=typename, _content=content)
            elif isinstance(obj, pd.Series):
                res = dict(_decode_type=typename, _content=obj.to_dict())
            if res:
                return res
        if type(obj) == int:
            return int(obj)
        elif type(obj) == float:
            return float(obj)
        elif type(obj) == bytes:
            return dict(_decode_type="bytes", _content=obj.hex())
        elif type(obj) == bytearray:
            return dict(_decode_type="bytearray", _content=obj.hex())
        elif type(obj) == complex and np is not None:
            encoded = b64encode(struct.pack("ff", np.real(obj), np.imag(obj)))
            encoded = "c" + encoded.decode("utf-8")
            return encoded
        return json.JSONEncoder.default(self, obj)


class BetterDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        super(BetterDecoder, self).__init__(object_hook=self.default, *args, **kwargs)

    def invalid_type(self):
        raise Exception("invalid _decode_type")

    def default(self, obj):
        if type(obj) == str and len(obj) == complex_number_length and obj[0] == "c":
            obj = np.array(struct.unpack("ff", b64decode(obj[1:])))
        if "_decode_type" in obj and obj["_decode_type"] == "numpy_complex":
            content = obj["_content"]
            shape = obj["_shape"]
            content = b64decode(content)
            content = struct.unpack("f" * (len(content) // 4), content)
            content = np.reshape(content, (-1, 2))
            content = content * complex1[None, :]
            content = np.sum(content, axis=1)
            content = np.reshape(content, shape)
            return content
        elif "_decode_type" in obj and obj["_decode_type"] == "bytes":
            return bytes.fromhex(obj["_content"])
        elif "_decode_type" in obj and obj["_decode_type"] == "bytearray":
            return bytearray.fromhex(obj["_content"])
        if pd is not None and isinstance(obj, dict):
            if "_decode_type" in obj and "_content" in obj:
                func = getattr(pd, obj["_decode_type"], self.invalid_type)
                obj = func(obj["_content"])
        return obj


def serialize(data):
    try:
        res = json.dumps(data, cls=BetterEncoder).encode('utf-8')
    except (TypeError, ValueError) as e:
        raise Exception('You can only send JSON-serializable data. Error is : %s' % e)
    return res


def deserialize(data):
    if type(data) == bytes:
        data = data.decode('utf-8')
    try:
        res = json.loads(data, cls=BetterDecoder)
    except (TypeError, ValueError) as e:
        raise Exception('Data received was not in JSON format. Error is %s' % str(e))
    return res
