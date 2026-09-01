# EEPROM findings

## Confirmed hardware case

The successful direct-VIN experiment used:

- Opel Corsa E receiving vehicle
- Daewoo IS `DWGM1004` donor radio
- GM part number `13435161`
- Variant marking `UH7-U2Q`
- Main PCB `OPEL JUNIOR`, `AGC-1088RN-R1.3`, part code `3151-00022`
- IC130 marked `24C128`

The comparison radio was a factory non-Bluetooth R 3.0 using main PCB `OSBX-S3001E MAIN REV:1.2`, part code `3151-00078`, with a 24C128-compatible IC130.

## VIN record

The record boundary was observed independently in both radio images:

```text
offset 0x1007:  AC             record tag
offset 0x1008:  16 bytes       encoded VIN value
offset 0x1018:  AD             next record tag
```

For a 17-character VIN indexed from 1 through 17:

```text
stored = VIN[10..17] + VIN[2..9]
```

The first character is not stored in this field. To reconstruct a display VIN, supply the known first character:

```text
VIN = first_character + stored[9..16] + stored[1..8]
```

The repository utility uses zero-based Python equivalents:

```python
stored = vin[9:17] + vin[1:9]
decoded = first_character + stored[8:16] + stored[0:8]
```

## Direct replacement result

A target image was built from the donor's complete authoritative image. Only the 16-byte VIN value was replaced; every byte outside `0x1008–0x1017` remained identical. The chip was written at 100 kHz and two complete post-write reads matched the intended 16 KiB image exactly. After resoldering and reassembly, the donor radio worked in the receiving vehicle.

This validates direct VIN replacement for the tested combination. It does not prove that every GM radio using a 24C128 shares this layout.

## Experimental cleared state

The original R 3.0 image was also used for a reversible experiment in which only `0x1008–0x1017` was changed to sixteen `FF` bytes. Two complete readbacks matched that intended image. The radio was not subsequently powered, so automatic VIN learning was not tested.

Consequently:

- The byte modification and readback are verified.
- The behavior of the R 3.0 firmware with that field is unverified.
- Calling the resulting image universally “virgin” would overstate the evidence.

Testing automatic learning in a vehicle would consume the cleared state if successful. A final sale-ready cleared state would then require another desolder, read, write, verification, and resolder cycle.

## Evidence boundaries

- No whole-image transplant between the non-Bluetooth and Bluetooth radios was tested.
- No unexplained random-looking or security-related region was modified.
- No rear USB or unauthenticated diagnostic programming route was identified.
- No checksum associated with the 16-byte VIN value was observed between its `AC` and `AD` tags.
- In-circuit reads were not used as authoritative write sources.
