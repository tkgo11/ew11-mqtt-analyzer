from __future__ import annotations

import random

from ew11_analyzer.checksums import _crc8_msb, _crc16_reflected, _sum8, _xor8, detect_checksum
from ew11_analyzer.sources.simulator import frame


def _mk_samples(chk_fn, size: int, n: int = 12, tail: int | None = 0xEE):
    rng = random.Random(7)
    samples = []
    for _ in range(n):
        body = bytes([rng.randint(0, 255) for _ in range(6)])
        v = chk_fn(body)
        trailer = v.to_bytes(size, "big")
        samples.append(body + trailer + (bytes([tail]) if tail is not None else b""))
    return samples


def test_xor_detected():
    samples = [frame(0x40, 0x01, 0x51, [i, 0x00]) for i in range(12)]
    matches = detect_checksum(samples)
    assert matches
    best = matches[0]
    assert best.algo == "xor"
    assert best.verified
    assert best.pos == len(samples[0]) - 2  # before ETX tail
    assert best.size == 1


def test_sum8_detected():
    samples = _mk_samples(_sum8, 1)
    matches = detect_checksum(samples)
    assert any(m.algo == "sum8" and m.verified for m in matches)


def test_crc16_modbus_detected():
    samples = _mk_samples(lambda d: _crc16_reflected(d, 0xA001, 0xFFFF), 2, tail=None)
    matches = detect_checksum(samples)
    assert any("crc16" in m.algo and m.size == 2 and m.verified for m in matches)


def test_crc8_detected():
    samples = _mk_samples(lambda d: _crc8_msb(d, 0x07, 0x00), 1)
    matches = detect_checksum(samples)
    assert any(m.algo == "crc8" and m.verified for m in matches)


def test_no_checksum_random_data():
    rng = random.Random(99)
    samples = [bytes(rng.randint(0, 255) for _ in range(12)) for _ in range(64)]
    matches = detect_checksum(samples)
    assert not any(m.verified for m in matches)


def test_too_few_samples():
    assert detect_checksum([b"\x01\x02\x03\x04", b"\x01\x02\x03\x05"]) == []


def test_mixed_lengths_returns_empty():
    assert detect_checksum([b"\x01\x02\x03\x04\x05", b"\x01\x02\x03\x04"]) == []


def test_crc16_endianness():
    # little-endian wire order should be reported
    rng = random.Random(3)
    samples = []
    for _ in range(10):
        body = bytes(rng.randint(0, 255) for _ in range(5))
        v = _crc16_reflected(body, 0xA001, 0xFFFF)
        samples.append(body + v.to_bytes(2, "little"))
    matches = detect_checksum(samples)
    assert any(m.algo == "crc16-modbus" and m.endian == "little" for m in matches)


def test_covered_range_skips_stx():
    # checksum covers bytes[2:] (skipping STX+LEN)
    rng = random.Random(11)
    samples = []
    for _ in range(12):
        data = bytes(rng.randint(0, 255) for _ in range(5))
        chk = _xor8(data)
        samples.append(b"\xf7\x08" + data + bytes([chk]))
    matches = detect_checksum(samples)
    assert any(m.algo == "xor" and m.covered_start == 2 and m.verified for m in matches)
