# Opel radio EEPROM notes and tools

This repository documents a reproducible EEPROM workflow used to adapt a used Opel/GM radio to a different vehicle VIN. It focuses on preserving recoverability: read the complete EEPROM out of circuit, require repeatable backups, change only understood bytes, and verify every write with independent full-chip readbacks.

The confirmed case was a Daewoo IS `DWGM1004` radio with a 24C128 EEPROM installed in an Opel Corsa E. Directly replacing its stored VIN field worked in the receiving vehicle.

## What is confirmed

- A 24C128 contains 128 Kbit, or 16,384 bytes.
- The VIN record begins with tag `0xAC` at offset `0x1007`.
- Its 16-byte value occupies offsets `0x1008` through `0x1017`.
- Tag `0xAD` follows immediately at offset `0x1018`; there is no checksum byte inside the VIN field.
- The first VIN character is omitted. Characters 10–17 are stored first, followed by characters 2–9.
- For a VIN represented as `A 0B1C2D3E 4F5G6H7I`, the EEPROM stores `4F5G6H7I0B1C2D3E`.
- On the tested radio, replacing only this field with the correctly encoded receiving VIN produced a working radio.

## What is experimental

Clearing only the 16-byte VIN value to `FF` may create a self-learning or “virgin” state on some radios. A Corsa E repair report describes VIN auto-coding after virginization, and a decoder vendor describes some Opel 24C128 radios as reset by editing the VIN. Neither source publishes a byte-level recipe for this exact R 3.0 variant.

Therefore, this repository exposes an explicit `clear` operation for controlled research, but does **not** claim that an `FF` VIN field is a proven or universally usable virgin image.

## Safe workflow

1. Disconnect the radio completely from the vehicle.
2. Identify the EEPROM and its pin-1 marker from the package and PCB—not from text orientation.
3. Prefer an out-of-circuit read. The tested donor produced inconsistent but apparently successful in-circuit reads because surrounding circuitry interfered with the I2C bus.
4. Read the complete 16 KiB EEPROM at least three times at 100 kHz.
5. Require identical file sizes, hashes, and byte contents.
6. Preserve untouched backups somewhere outside the working directory.
7. Inspect or patch a copy only.
8. Before writing, make a fresh read and prove that it matches the expected physical chip.
9. After writing, perform at least two complete readbacks and compare both with the intended image.

Never power the radio and programmer simultaneously. Do not increase the EEPROM voltage merely because an in-circuit read fails.

## VIN utility

The Python utility has no third-party dependencies. Use [uv](https://docs.astral.sh/uv/) to select the pinned Python 3.12 interpreter:

```sh
uv run --no-project python scripts/eeprom_vin.py inspect radio.bin --first-character W
uv run --no-project python scripts/eeprom_vin.py patch radio.bin patched.bin W0000000000000000
uv run --no-project python scripts/eeprom_vin.py clear radio.bin experimental-clear.bin
```

`patch` and `clear` refuse to overwrite an existing output file. They validate the 16 KiB image and the surrounding `AC`/`AD` record tags, print SHA-256 hashes, and prove that changes are confined to the VIN field.

The `clear` command is deliberately described as experimental in its output.

## Configured repair workflow

`scripts/radio.py` uses environment variables for vehicle details, expected-image hashes, programmer location, and private storage. It has no third-party Python dependencies and runs from the repository root using the pinned Python 3.12 interpreter. With a suitable Python installation, `python3` can replace `uv run --no-project python`. It expects a compatible `ch341eeprom` executable, such as [stefanct/ch341eepromtool](https://github.com/stefanct/ch341eepromtool), using its standard 100 kHz speed.

Keep private data in `debug/`. This workspace ignores `debug/` through its global Git ignore configuration; the repository does not add a local ignore rule. On another machine, configure the same global rule and verify it before copying private files:

```sh
git check-ignore -v debug/config.env
mkdir -p debug
cp config.env.example debug/config.env
```

Fill in `debug/config.env` with your own values. Use shell quoting for values containing spaces. Load only a configuration file you trust:

```sh
set -a
. ./debug/config.env
set +a
```

| Variable | Purpose |
|---|---|
| `RADIO_DATA_DIR` | Private storage root for generated images and operation records, usually `debug` |
| `RADIO_PROGRAMMER` | Executable path or command name of the CH341A tool |
| `RADIO_TARGET_VIN` | Receiving vehicle's 17-character VIN |
| `RADIO_FIRST_CHARACTER` | Known first VIN character for inspection; it is omitted from the EEPROM field |
| `RADIO_DONOR_IMAGE`, `RADIO_DONOR_SHA256` | Authoritative donor backup and independently verified SHA-256 |
| `RADIO_ORIGINAL_IMAGE`, `RADIO_ORIGINAL_SHA256` | Authoritative original-radio backup and independently verified SHA-256 |

Paths are relative to the working directory unless absolute. Preserve the baseline hashes after independently verifying the backups; do not regenerate them automatically to accept a changed file. New read operations do not require configured backups.

Read three independent copies of a physically identified chip:

```sh
uv run --no-project python scripts/radio.py read donor
uv run --no-project python scripts/radio.py read original
```

Read operations require confirmation, reject uniform or inconsistent contents, and save uniquely named records under `$RADIO_DATA_DIR/records/`. Verified images are made read-only. After choosing authoritative backups, set their paths and hashes in the private configuration.

Inspect a verified backup or build the donor's target image:

```sh
uv run --no-project python scripts/radio.py inspect donor
uv run --no-project python scripts/radio.py inspect original
uv run --no-project python scripts/radio.py patch donor
```

Donor patching verifies both backup hashes and requires the original radio's stored VIN to corroborate `RADIO_TARGET_VIN`. It modifies only the 16-byte VIN field. The output is `$RADIO_DATA_DIR/images/donor-vin.bin`; repeating the build accepts identical output but refuses to overwrite different contents.

Program the donor only after reviewing the physical chip and target image:

```sh
uv run --no-project python scripts/radio.py write donor --target debug/images/donor-vin.bin
```

The writer requires the target to exactly equal the configured VIN-only modification, preserves expected and target images, and reads the seated chip before writing. An unknown chip is rejected. A chip already containing the target is verified twice without writing. Otherwise, a separate typed write confirmation is required, followed by two complete readbacks that must match the target.

The experimental original-radio operation remains explicit:

```sh
uv run --no-project python scripts/radio.py clear original
uv run --no-project python scripts/radio.py write original --target debug/images/original-cleared.bin --experimental-clear
```

Clearing the field does not prove automatic VIN learning. A write requires the separate `WRITE EXPERIMENTAL CLEAR ORIGINAL` confirmation. Do not repeat an already verified physical operation just because the tools have moved.

The workflow does not invoke `sudo`. If your programmer requires elevated privileges, preserve only the documented configuration variables when running it under your system's privilege mechanism. Check voltage, wiring, and pin orientation before every hardware session.

Back up `debug/` separately: ignored files are not uploaded to GitHub or recovered by cloning the public repository. Keep real identifiers, EEPROM images, photographs, operation records, and personal repair notes out of tracked files. The private configuration is the only place to maintain your vehicle-specific setup.

## Hardware notes

See [docs/hardware.md](docs/hardware.md) for the standard SOIC-8 pinout and the CH341A checks used during this investigation. See [docs/findings.md](docs/findings.md) for the byte-level findings and evidence boundaries.

No real EEPROM dumps, vehicle VINs, radio serial numbers, write records, or original photographs are included in this repository.

## Tests

```sh
uv run --no-project python -m unittest discover -s tests -v
```

The tests use synthetic 16 KiB images and a fake programmer. They check chip identity, VIN-only targets, explicit confirmation, failed reads, readback verification, experimental clearing, and repeat operations without accessing hardware or containing vehicle data.

## Sources

- [Documented GM/Daewoo DWGM1002 24C128 VIN replacement procedure](https://cobaltr4.ru/%D0%BF%D0%B5%D1%80%D0%B5%D0%BF%D1%80%D0%B8%D0%B2%D1%8F%D0%B7%D0%BA%D0%B0-%D1%88%D1%82%D0%B0%D1%82%D0%BD%D0%BE%D0%B9-gm-%D0%BC%D0%B0%D0%B3%D0%BD%D0%B8%D1%82%D0%BE%D0%BB%D1%8B-%D0%BA-vin-%D0%BA%D0%BE/)
- [Corsa E report describing auto-coding after EEPROM virginization](https://www.tlemcen-electronic.com/forum/tableau-de-bord-habitacle-and-securit-conducteur/autoradio-et-navigateur-gps/117524-poste-radio-locked-opel-corsa.html)
- [Pecky's Decoder coverage notes](https://peckys-decoder.com/coverage.php)
- [Open-source CH341A EEPROM tool](https://github.com/stefanct/ch341eepromtool)

## Disclaimer

This is independent repair research, not an Opel, Vauxhall, General Motors, Daewoo IS, or WCH publication. Use it only on hardware you own or are authorized to repair. Keep a verified original backup and accept that hardware modification always carries risk.
