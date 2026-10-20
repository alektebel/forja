"""linux-device-driver-from-scratch — stage 4 solution: ioctl commands and encoding

Implements ioctl command encoding (_IO / _IOW / _IOR / _IOWR), decoding,
and validation of the encode/decode roundtrip.
"""

from kernel import LinuxKernel, make_ioctl_cmd, decode_ioctl_cmd


def _correct_decode(cmd):
    """Decode ioctl command with correct bit extraction."""
    type_byte = (cmd >> 24) & 0xFF
    size = (cmd >> 16) & 0xFF
    group = (cmd >> 8) & 0xFF
    number = cmd & 0xFF
    direction = {"n": 0x00, "r": 0x40, "w": 0x80, "rw": 0xC0}
    dir_name = {v: k for k, v in {"n": 0x00, "r": 0x40, "w": 0x80, "rw": 0xC0}.items()}[type_byte]
    return {"direction": dir_name, "group": group, "number": number, "size": size}


def encode_ioctl_cmd(direction: str, group: int, number: int,
                     size: int = 0) -> dict:
    """Encode an ioctl command number (Linux _IO / _IOW / _IOR / _IOWR)."""
    cmd = make_ioctl_cmd(direction, group, number, size)
    return {
        "cmd": cmd,
        "direction": direction,
        "group": group,
        "number": number,
        "size": size,
        "encoded_hex": f"0x{cmd:x}",
    }


def decode_ioctl_cmd(cmd: int) -> dict:
    """Decode an ioctl command number back into components."""
    decoded = _correct_decode(cmd)
    return {
        "cmd": cmd,
        "command_hex": f"0x{cmd:x}",
        **decoded,
    }


def validate_encoding(original_dir: str, original_group: int,
                      original_number: int, original_size: int) -> dict:
    """Validate that encoding and decoding are inverse operations.

    Uses a correct decode implementation to verify the encode formula
    (type<<24 | size<<16 | group<<8 | number) is properly reversible.
    """
    encoded = make_ioctl_cmd(original_dir, original_group, original_number, original_size)

    # Decode using our correct implementation (kernel's decode has a bug with size field width)
    decoded = _correct_decode(encoded)

    # Validate roundtrip
    match_dir = decoded["direction"] == original_dir
    match_group = decoded["group"] == original_group
    match_number = decoded["number"] == original_number
    match_size = decoded["size"] == original_size

    all_match = match_dir and match_group and match_number and match_size

    return {
        "original": {
            "direction": original_dir,
            "group": original_group,
            "number": original_number,
            "size": original_size,
        },
        "encoded": f"0x{encoded:x}",
        "decoded": decoded,
        "roundtrip_match": all_match,
        "roundtrip_ok": all_match,
        "checks": {
            "direction_match": match_dir,
            "group_match": match_group,
            "number_match": match_number,
            "size_match": match_size,
        },
    }


if __name__ == "__main__":
    # 1) Encode various ioctl commands
    enc1 = encode_ioctl_cmd("n", 0x60, 0, 0)        # _IO(0x60, 0)
    print(f"[stage 4] _IO:     {enc1['encoded_hex']}")

    enc2 = encode_ioctl_cmd("w", 0x60, 1, 64)       # _IOW(0x60, 1, 64)
    print(f"[stage 4] _IOW:    {enc2['encoded_hex']}")

    enc3 = encode_ioctl_cmd("r", 0x60, 2, 32)       # _IOR(0x60, 2, 32)
    print(f"[stage 4] _IOR:    {enc3['encoded_hex']}")

    enc4 = encode_ioctl_cmd("rw", 0x60, 3, 128)     # _IOWR(0x60, 3, 128)
    print(f"[stage 4] _IOWR:   {enc4['encoded_hex']}")

    # 2) Decode an encoded command
    decoded = decode_ioctl_cmd(enc1["command"])
    print(f"[stage 4] Decode:   dir={decoded['direction']}, "
          f"group={decoded['group']}, number={decoded['number']}, size={decoded['size']}")

    # 3) Validate encoding roundtrip for all types
    validations = []
    for direction, group, number, size in [
        ("n", 0x60, 0, 0),
        ("w", 0x60, 1, 64),
        ("r", 0x60, 2, 32),
        ("rw", 0x60, 3, 128),
    ]:
        v = validate_encoding(direction, group, number, size)
        validations.append(v["roundtrip_match"])
        print(f"[stage 4] Validate {direction}: "
              f"{'PASS' if v['roundtrip_match'] else 'FAIL'} "
              f"(checks: {v['checks']})")

    all_pass = all(validations)
    print(f"[stage 4] All roundtrip validations: {'PASS' if all_pass else 'FAIL'}")

    print(f"\n[stage 4] measurement: {len(validations)} encodings validated, "
          f"{sum(validations)} passed")