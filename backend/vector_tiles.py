"""Bounded reader for the MVT layers used by Vessel (vector-tile spec 2.1).

No rendering or network dependencies: unknown layers and fields are skipped.
Coordinates retain MVT's downward Y axis and polygon winding, including holes.
"""

import struct

MAX_BYTES = 4 << 20
MAX_POINTS = 250_000
LAYERS = {"water", "waterway", "transportation", "place"}


def varint(data, pos):
    """Read one protobuf unsigned integer and return the next byte position."""
    value = 0
    for shift in range(0, 70, 7):
        if pos >= len(data):
            raise ValueError("Truncated vector tile")
        byte = data[pos]
        pos += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, pos
    raise ValueError("Invalid vector integer")


def fields(data):
    """Yield (field number, wire type, value), checking every byte boundary.

    Protobuf wire types: 0 = varint, 1 = fixed64, 2 = bytes, 5 = fixed32.
    Length-delimited values remain bytes for the layer/feature reader to decode.
    """
    pos = 0
    while pos < len(data):
        tag, pos = varint(data, pos)
        field, wire = tag >> 3, tag & 7
        if not field:
            raise ValueError("Invalid vector field")
        if wire == 0:
            value, pos = varint(data, pos)
        elif wire in (1, 2, 5):
            if wire == 2:
                size, pos = varint(data, pos)
            else:
                size = 8 if wire == 1 else 4
            end = pos + size
            if end > len(data):
                raise ValueError("Truncated vector field")
            value, pos = data[pos:end], end
        else:
            raise ValueError("Unsupported vector wire type")
        yield field, wire, value


def packed(data):
    """Unpack consecutive integers from a tags or geometry byte field."""
    pos = 0
    while pos < len(data):
        value, pos = varint(data, pos)
        yield value


def zigzag(value):
    """Decode MVT's signed deltas: 0, 1, 2, 3 become 0, -1, 1, -2."""
    return (value >> 1) ^ -(value & 1)


def scalar(data):
    """Read the typed value stored in a layer's attribute dictionary."""
    for field, wire, value in fields(data):
        if field == 1 and wire == 2:
            return value.decode("utf-8", errors="replace")[:200]
        if (field, wire) in ((2, 5), (3, 1)):
            return struct.unpack("<f" if field == 2 else "<d", value)[0]
        if wire == 0 and field in (4, 5, 6, 7):
            return zigzag(value) if field == 6 else value
    return None


def paths(data, kind, budget):
    """Expand MoveTo (1), LineTo (2) and ClosePath (7) into point lists.

    The delta cursor continues across rings. The shared one-item budget is
    decremented across all features so many small paths cannot evade the cap.
    """
    values = iter(packed(data))
    x = y = 0
    result = []
    closed = False
    try:
        for command in values:
            op, count = command & 7, command >> 3
            if count < 1 or count > MAX_POINTS:
                raise ValueError("Invalid vector command")
            if op == 7:
                if (
                    count != 1
                    or kind != 3
                    or not result
                    or len(result[-1]) < 3
                    or closed
                ):
                    raise ValueError("Invalid polygon closure")
                # Closing a ring materializes a point too; count it in the cap.
                budget[0] -= 1
                if budget[0] < 0:
                    raise ValueError("Vector tile has too many points")
                result[-1].append(result[-1][0])
                closed = True
                continue
            if op not in (1, 2) or (op == 2 and (not result or closed)):
                raise ValueError("Invalid vector path")
            budget[0] -= count
            if budget[0] < 0:
                raise ValueError("Vector tile has too many points")
            for _ in range(count):
                dx, dy = next(values), next(values)
                x += zigzag(dx)
                y += zigzag(dy)
                if abs(x) > 1_000_000 or abs(y) > 1_000_000:
                    raise ValueError("Vector coordinate out of range")
                if op == 1:
                    result.append([])
                    closed = False
                result[-1].append([x, y])
    except StopIteration as error:
        raise ValueError("Truncated vector path") from error
    return result


def field_values(entries, number, wire_type):
    """Select repeated fields without losing their dictionary/feature order."""
    return [
        value for field, wire, value in entries if (field, wire) == (number, wire_type)
    ]


def feature(data, keys, values, budget):
    """Resolve dictionary tags and geometry for one feature in a known layer."""
    properties, kind, geometry = {}, 0, b""
    for number, wire, value in fields(data):
        if (number, wire) == (2, 2):
            # Tags alternate key and value indices into the parent layer.
            tags = list(packed(value))
            if len(tags) % 2:
                raise ValueError("Unpaired vector tags")
            for index in range(0, len(tags), 2):
                key_index, value_index = tags[index : index + 2]
                if key_index >= len(keys) or value_index >= len(values):
                    raise ValueError("Invalid vector tag index")
                properties[keys[key_index]] = values[value_index]
        elif (number, wire) == (3, 0):
            kind = value
        elif (number, wire) == (4, 2):
            geometry += value
    if kind in (1, 2, 3):  # Point, LineString, Polygon; unknown kinds are skipped.
        return properties, kind, paths(geometry, kind, budget)
    return None


def decode(data):
    """Yield (layer name, properties, geometry kind, extent, paths) per feature.

    Coordinates stay in tile units (usually 0..4096, with a small buffer).
    detail_map.project_tile clips the buffer and converts to nautical units.
    """
    if len(data) > MAX_BYTES:
        raise ValueError("Vector tile too large")
    budget = [MAX_POINTS]
    for layer in field_values(list(fields(data)), 3, 2):
        entries = list(fields(layer))
        names = field_values(entries, 1, 2)
        name = names[0].decode("utf-8") if names else ""
        if name not in LAYERS:
            continue
        version = next(iter(field_values(entries, 15, 0)), 1)
        extent = next(iter(field_values(entries, 5, 0)), 4096)
        if version not in (1, 2) or not 1 <= extent <= 65536:
            raise ValueError("Unsupported vector layer")

        # MVT stores each string/value once per layer and features refer to indices.
        keys = [
            raw.decode("utf-8", errors="replace") for raw in field_values(entries, 3, 2)
        ]
        values = [scalar(raw) for raw in field_values(entries, 4, 2)]
        for raw in field_values(entries, 2, 2):
            decoded = feature(raw, keys, values, budget)
            if decoded is not None:
                properties, kind, geometry = decoded
                yield name, properties, kind, extent, geometry
