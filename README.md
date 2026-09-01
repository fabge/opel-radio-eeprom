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

The Python utility has no third-party dependencies:

```sh
python3 scripts/eeprom_vin.py inspect radio.bin --first-character W
python3 scripts/eeprom_vin.py patch radio.bin patched.bin W0000000000000000
python3 scripts/eeprom_vin.py clear radio.bin experimental-clear.bin
```

`patch` and `clear` refuse to overwrite an existing output file. They validate the 16 KiB image and the surrounding `AC`/`AD` record tags, print SHA-256 hashes, and prove that changes are confined to the VIN field.

The `clear` command is deliberately described as experimental in its output.

## CH341A helper scripts

The shell wrappers expect a compatible `ch341eeprom` executable, such as [stefanct/ch341eepromtool](https://github.com/stefanct/ch341eepromtool). They do not contain passwords or invoke `sudo` themselves.

Read three independent copies:

```sh
sudo ./scripts/read-24c128.sh /path/to/ch341eeprom ./read-record
```

Perform a guarded write, where `expected-current.bin` must exactly match the fresh pre-write chip read:

```sh
sudo ./scripts/write-24c128-guarded.sh \
  /path/to/ch341eeprom \
  expected-current.bin \
  intended-target.bin \
  ./write-record
```

Review both shell scripts before using them. A wiring, voltage, orientation, chip-selection, or image-selection mistake can damage hardware or destroy recoverable data.

## Hardware notes

See [docs/hardware.md](docs/hardware.md) for the standard SOIC-8 pinout and the CH341A checks used during this investigation. See [docs/findings.md](docs/findings.md) for the byte-level findings and evidence boundaries.

No real EEPROM dumps, vehicle VINs, radio serial numbers, write records, or original photographs are included in this repository.

## Tests

```sh
python3 -m unittest discover -s tests -v
sh -n scripts/read-24c128.sh
sh -n scripts/write-24c128-guarded.sh
```

The tests construct synthetic 16 KiB images in memory. They do not contain vehicle data.

## Sources

- [Documented GM/Daewoo DWGM1002 24C128 VIN replacement procedure](https://cobaltr4.ru/%D0%BF%D0%B5%D1%80%D0%B5%D0%BF%D1%80%D0%B8%D0%B2%D1%8F%D0%B7%D0%BA%D0%B0-%D1%88%D1%82%D0%B0%D1%82%D0%BD%D0%BE%D0%B9-gm-%D0%BC%D0%B0%D0%B3%D0%BD%D0%B8%D1%82%D0%BE%D0%BB%D1%8B-%D0%BA-vin-%D0%BA%D0%BE/)
- [Corsa E report describing auto-coding after EEPROM virginization](https://www.tlemcen-electronic.com/forum/tableau-de-bord-habitacle-and-securit-conducteur/autoradio-et-navigateur-gps/117524-poste-radio-locked-opel-corsa.html)
- [Pecky's Decoder coverage notes](https://peckys-decoder.com/coverage.php)
- [Open-source CH341A EEPROM tool](https://github.com/stefanct/ch341eepromtool)

## Disclaimer

This is independent repair research, not an Opel, Vauxhall, General Motors, Daewoo IS, or WCH publication. Use it only on hardware you own or are authorized to repair. Keep a verified original backup and accept that hardware modification always carries risk.
