#!/usr/bin/env python3
"""Inspect or modify the tagged VIN field found in tested Opel radio EEPROMs."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

EEPROM_SIZE = 16_384
DEFAULT_OFFSET = 0x1008
FIELD_LENGTH = 16
VIN_PATTERN = re.compile(r"[A-HJ-NPR-Z0-9]{17}")


def parse_offset(value: str) -> int:
    try:
        offset = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid offset: {value}") from exc
    if offset < 1 or offset + FIELD_LENGTH >= EEPROM_SIZE:
        raise argparse.ArgumentTypeError("offset leaves no room for AC/value/AD record")
    return offset


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_image(path: Path) -> bytes:
    data = path.read_bytes()
    if len(data) != EEPROM_SIZE:
        raise ValueError(f"{path} is {len(data)} bytes; expected {EEPROM_SIZE}")
    return data


def validate_record(data: bytes, offset: int) -> None:
    before = data[offset - 1]
    after = data[offset + FIELD_LENGTH]
    if before != 0xAC or after != 0xAD:
        raise ValueError(
            f"expected AC/value/AD record around 0x{offset:04X}; found {before:02X}/value/{after:02X}",
        )


def encode_vin(vin: str) -> bytes:
    normalized = vin.upper()
    if not VIN_PATTERN.fullmatch(normalized):
        raise ValueError("VIN must be 17 characters using VIN-safe uppercase letters and digits")
    return (normalized[9:17] + normalized[1:9]).encode("ascii")


def decode_field(field: bytes, first_character: str) -> str:
    if len(field) != FIELD_LENGTH:
        raise ValueError("stored VIN field must be exactly 16 bytes")
    first = first_character.upper()
    if len(first) != 1 or not re.fullmatch(r"[A-HJ-NPR-Z0-9]", first):
        raise ValueError("first VIN character must be one VIN-safe letter or digit")
    text = field.decode("ascii")
    return first + text[8:16] + text[0:8]


def changed_offsets(before: bytes, after: bytes) -> list[int]:
    return [index for index, pair in enumerate(zip(before, after, strict=True)) if pair[0] != pair[1]]


def build_modified(data: bytes, offset: int, replacement: bytes) -> bytes:
    if len(replacement) != FIELD_LENGTH:
        raise ValueError("replacement field must be exactly 16 bytes")
    result = bytearray(data)
    result[offset : offset + FIELD_LENGTH] = replacement
    return bytes(result)


def write_new_image(path: Path, data: bytes) -> None:
    with path.open("xb") as output:
        output.write(data)


def report_change(source: bytes, result: bytes, offset: int) -> None:
    changes = changed_offsets(source, result)
    allowed = range(offset, offset + FIELD_LENGTH)
    if any(index not in allowed for index in changes):
        raise RuntimeError("internal error: output differs outside the VIN field")
    print(f"Source SHA-256: {sha256(source)}")
    print(f"Output SHA-256: {sha256(result)}")
    print(f"Changed bytes: {len(changes)}; all within 0x{offset:04X}-0x{offset + 15:04X}")


def inspect_command(args: argparse.Namespace) -> None:
    data = read_image(args.image)
    validate_record(data, args.offset)
    field = data[args.offset : args.offset + FIELD_LENGTH]
    print(f"Image SHA-256: {sha256(data)}")
    print(f"Stored field: {field.hex()}")
    if field == b"\xff" * FIELD_LENGTH:
        print("Field state: erased (FF); automatic VIN learning is not guaranteed")
        return
    try:
        vin = decode_field(field, args.first_character)
    except UnicodeDecodeError:
        print("Decoded VIN: unavailable; field is not ASCII")
    else:
        print(f"Decoded VIN: {vin}")


def patch_command(args: argparse.Namespace) -> None:
    source = read_image(args.source)
    validate_record(source, args.offset)
    result = build_modified(source, args.offset, encode_vin(args.vin))
    write_new_image(args.output, result)
    report_change(source, result, args.offset)
    print(f"Wrote: {args.output}")


def clear_command(args: argparse.Namespace) -> None:
    source = read_image(args.source)
    validate_record(source, args.offset)
    result = build_modified(source, args.offset, b"\xff" * FIELD_LENGTH)
    write_new_image(args.output, result)
    report_change(source, result, args.offset)
    print("EXPERIMENTAL: an FF VIN field is not proven to auto-learn on every radio")
    print(f"Wrote: {args.output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="inspect and decode the VIN field")
    inspect_parser.add_argument("image", type=Path)
    inspect_parser.add_argument(
        "--first-character",
        required=True,
        help="the known first VIN character, which is not stored in this field",
    )
    inspect_parser.add_argument("--offset", type=parse_offset, default=DEFAULT_OFFSET)
    inspect_parser.set_defaults(handler=inspect_command)

    patch_parser = subparsers.add_parser("patch", help="write an encoded VIN into a new image")
    patch_parser.add_argument("source", type=Path)
    patch_parser.add_argument("output", type=Path)
    patch_parser.add_argument("vin")
    patch_parser.add_argument("--offset", type=parse_offset, default=DEFAULT_OFFSET)
    patch_parser.set_defaults(handler=patch_command)

    clear_parser = subparsers.add_parser(
        "clear",
        help="EXPERIMENTAL: replace only the VIN value with FF in a new image",
    )
    clear_parser.add_argument("source", type=Path)
    clear_parser.add_argument("output", type=Path)
    clear_parser.add_argument("--offset", type=parse_offset, default=DEFAULT_OFFSET)
    clear_parser.set_defaults(handler=clear_command)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
