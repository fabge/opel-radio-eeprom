#!/usr/bin/env python3
"""Environment-configured Opel radio EEPROM workflow."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import eeprom_vin as vin


def setting(name: str) -> str:
    value = os.environ.get(f"RADIO_{name}", "").strip()
    if not value:
        raise ValueError(f"Set RADIO_{name}")
    return value


def image(path: Path) -> bytes:
    data = vin.read_image(path)
    if len(set(data)) == 1:
        raise ValueError(f"{path}: uniform EEPROM contents; treat as a failed read")
    return data


def expected(profile: str) -> bytes:
    data = image(Path(setting(f"{profile.upper()}_IMAGE")))
    digest = setting(f"{profile.upper()}_SHA256").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", digest) or vin.sha256(data) != digest:
        raise ValueError(f"{profile}: expected-image SHA-256 mismatch")
    vin.validate_record(data, vin.DEFAULT_OFFSET)
    return data


def candidate(profile: str, clear: bool = False) -> bytes:
    source = expected(profile)
    if clear:
        replacement = b"\xff" * vin.FIELD_LENGTH
    else:
        target_vin = setting("TARGET_VIN")
        replacement = vin.encode_vin(target_vin)
        if profile == "donor":
            original = expected("original")
            start = vin.DEFAULT_OFFSET
            if original[start : start + vin.FIELD_LENGTH] != replacement:
                raise ValueError("Target VIN is not corroborated by the original-radio backup")
    return vin.build_modified(source, vin.DEFAULT_OFFSET, replacement)


def record_directory(profile: str, operation: str) -> Path:
    root = Path(setting("DATA_DIR")) / "records"
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(tempfile.mkdtemp(prefix=f"{stamp}-{profile}-{operation}-", dir=root))


def programmer() -> str:
    configured = setting("PROGRAMMER")
    executable = shutil.which(configured)
    if executable is None:
        raise ValueError("RADIO_PROGRAMMER must name an executable ch341eeprom tool")
    return executable


def chip_read(executable: str, destination: Path) -> bytes:
    if destination.exists():
        raise ValueError(f"Refusing to overwrite {destination}")
    subprocess.run([executable, "-v", "-s", "24c128", "-r", str(destination)], check=True)
    data = image(destination)
    destination.chmod(0o444)
    return data


def confirm(phrase: str) -> None:
    print("Radio disconnected and unpowered; verify 3.3 V, chip identity and pin 1.")
    if input(f"Type {phrase} to continue: ") != phrase:
        raise ValueError("Cancelled")


def read(profile: str) -> None:
    executable = programmer()
    confirm(f"READ {profile.upper()}")
    directory = record_directory(profile, "read")
    print(f"Records: {directory}")
    copies = [chip_read(executable, directory / f"read-0{i}.bin") for i in range(1, 4)]
    if copies[0] != copies[1] or copies[0] != copies[2]:
        raise ValueError("The three reads differ; preserve them and do not write")
    print(f"SUCCESS: three identical 16 KiB reads; SHA-256: {vin.sha256(copies[0])}")


def build(profile: str, clear: bool) -> None:
    data = candidate(profile, clear)
    directory = Path(setting("DATA_DIR")) / "images"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / f"{profile}-{'cleared' if clear else 'vin'}.bin"
    if output.exists():
        if output.read_bytes() != data:
            raise ValueError(f"Refusing to overwrite a different image: {output}")
    else:
        vin.write_new_image(output, data)
    output.chmod(0o444)
    vin.report_change(expected(profile), data, vin.DEFAULT_OFFSET)
    if clear:
        print("EXPERIMENTAL: automatic VIN learning has not been proven")
    print(f"Image: {output}")


def write(profile: str, target_path: Path, experimental_clear: bool) -> None:
    source = expected(profile)
    target = image(target_path)
    if target != candidate(profile, experimental_clear):
        raise ValueError("Target must exactly match the configured VIN-only modification")
    executable = programmer()
    directory = record_directory(profile, "write")
    print(f"Records: {directory}")
    for name, data in [("expected-current.bin", source), ("intended-target.bin", target)]:
        destination = directory / name
        vin.write_new_image(destination, data)
        destination.chmod(0o444)
    confirm(f"CHECK {profile.upper()}")
    current = chip_read(executable, directory / "prewrite-read.bin")
    if current == target:
        second = chip_read(executable, directory / "already-target-read.bin")
        if second != target:
            raise ValueError("Readbacks differ; preserve records and do not install the chip")
        print("SUCCESS: chip already matches target, verified twice; no write performed")
        return
    if current != source:
        raise ValueError("Seated chip does not match the configured backup; no write performed")
    vin.report_change(source, target, vin.DEFAULT_OFFSET)
    if experimental_clear:
        print("EXPERIMENTAL: clearing the VIN does not guarantee automatic learning")
    confirm(f"WRITE {'EXPERIMENTAL CLEAR ' if experimental_clear else ''}{profile.upper()}")
    subprocess.run(
        [executable, "-v", "-s", "24c128", "-w", str(directory / "intended-target.bin")],
        check=True,
    )
    copies = [chip_read(executable, directory / f"postwrite-read-0{i}.bin") for i in range(1, 3)]
    if any(data != target for data in copies):
        raise ValueError("Post-write verification failed; preserve records and do not install the chip")
    print("SUCCESS: two complete readbacks match the target")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ["read", "inspect", "patch", "clear", "write"]:
        command = commands.add_parser(name)
        command.add_argument("profile", choices=["donor", "original"])
        if name == "write":
            command.add_argument("--target", required=True, type=Path)
            command.add_argument("--experimental-clear", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "read":
            read(args.profile)
        elif args.command == "inspect":
            expected(args.profile)
            vin.inspect_command(
                argparse.Namespace(
                    image=Path(setting(f"{args.profile.upper()}_IMAGE")),
                    offset=vin.DEFAULT_OFFSET,
                    first_character=setting("FIRST_CHARACTER"),
                ),
            )
        elif args.command in {"patch", "clear"}:
            build(args.profile, args.command == "clear")
        else:
            write(args.profile, args.target, args.experimental_clear)
    except (OSError, ValueError, RuntimeError, EOFError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
