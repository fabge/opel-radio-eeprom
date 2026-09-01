# Hardware and connection notes

## Standard 24C128 SOIC-8 pinout

Viewed from the top of the package, with the pin-1 dot or notch at the top:

```text
             ┌───────┐
       A0  1 │ •     │ 8  VCC
       A1  2 │       │ 7  WP
       A2  3 │       │ 6  SCL
      GND  4 │       │ 5  SDA
             └───────┘
```

Package text is not a reliable orientation guide. PCBs may mount the same device in different rotations. Use the molded package marker and the PCB pin-1 marker, then confirm the adapter path with continuity measurements while everything is unpowered.

## Voltage checks used in the confirmed setup

The tested setup used a black/gold CH341A programmer and a 24-series adapter path measured at approximately 3.3 V. Before attaching a target, measurements relative to pin 4/GND should establish:

- Pin 8/VCC is approximately 3.3 V.
- Pin 5/SDA does not rise materially above 3.3 V.
- Pin 6/SCL does not rise materially above 3.3 V.

Disconnect USB before attaching, removing, or repositioning the EEPROM. Check for an accidental VCC-to-GND short before reconnecting USB.

The common red stripe on an SOIC clip often denotes pin 1, but color alone is not proof. Adapter boards and cable assemblies can reverse or remap connections.

## Why out-of-circuit reading matters

Three successful-looking in-circuit reads of the tested donor differed at both 100 kHz and 400 kHz. The surrounding PCB was loading or interacting with the I2C bus. After desoldering the EEPROM, three independent 100 kHz reads were byte-for-byte identical.

Treat a programmer's “read succeeded” message only as evidence that a transaction completed. Repeatability across full-chip images is the evidence that the data is trustworthy.

## Power isolation

- Keep the radio disconnected from the vehicle while the programmer supplies the EEPROM.
- Never connect vehicle power and programmer power simultaneously.
- Do not apply 5 V or 1.8 V merely as a troubleshooting experiment.
- Do not power an opened radio unless it has been reassembled sufficiently to prevent shorts.
