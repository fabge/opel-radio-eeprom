import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import eeprom_vin

TEST_VIN = "W00000000A1234567"


def synthetic_image() -> bytes:
    data = bytearray([0x55] * eeprom_vin.EEPROM_SIZE)
    offset = eeprom_vin.DEFAULT_OFFSET
    data[offset - 1] = 0xAC
    data[offset : offset + eeprom_vin.FIELD_LENGTH] = eeprom_vin.encode_vin(TEST_VIN)
    data[offset + eeprom_vin.FIELD_LENGTH] = 0xAD
    return bytes(data)


class VinEncodingTests(unittest.TestCase):
    def test_encode_and_decode_round_trip(self):
        encoded = eeprom_vin.encode_vin(TEST_VIN)
        self.assertEqual(encoded, b"A123456700000000")
        self.assertEqual(eeprom_vin.decode_field(encoded, "W"), TEST_VIN)

    def test_rejects_invalid_vin_characters(self):
        with self.assertRaises(ValueError):
            eeprom_vin.encode_vin("W00000000I1234567")


class ImageModificationTests(unittest.TestCase):
    def test_patch_changes_only_vin_field(self):
        source = synthetic_image()
        replacement = eeprom_vin.encode_vin("W11111111B7654321")
        result = eeprom_vin.build_modified(source, eeprom_vin.DEFAULT_OFFSET, replacement)
        changes = eeprom_vin.changed_offsets(source, result)
        self.assertTrue(changes)
        self.assertTrue(
            all(eeprom_vin.DEFAULT_OFFSET <= index < eeprom_vin.DEFAULT_OFFSET + eeprom_vin.FIELD_LENGTH for index in changes),
        )
        eeprom_vin.validate_record(result, eeprom_vin.DEFAULT_OFFSET)

    def test_clear_changes_only_vin_field(self):
        source = synthetic_image()
        result = eeprom_vin.build_modified(
            source,
            eeprom_vin.DEFAULT_OFFSET,
            b"\xff" * eeprom_vin.FIELD_LENGTH,
        )
        self.assertEqual(
            result[eeprom_vin.DEFAULT_OFFSET : eeprom_vin.DEFAULT_OFFSET + eeprom_vin.FIELD_LENGTH],
            b"\xff" * eeprom_vin.FIELD_LENGTH,
        )
        self.assertEqual(
            source[: eeprom_vin.DEFAULT_OFFSET],
            result[: eeprom_vin.DEFAULT_OFFSET],
        )
        self.assertEqual(
            source[eeprom_vin.DEFAULT_OFFSET + eeprom_vin.FIELD_LENGTH :],
            result[eeprom_vin.DEFAULT_OFFSET + eeprom_vin.FIELD_LENGTH :],
        )

    def test_rejects_missing_record_tags(self):
        data = bytearray(synthetic_image())
        data[eeprom_vin.DEFAULT_OFFSET - 1] = 0x00
        with self.assertRaises(ValueError):
            eeprom_vin.validate_record(bytes(data), eeprom_vin.DEFAULT_OFFSET)

    def test_output_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.bin"
            output.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                eeprom_vin.write_new_image(output, synthetic_image())


if __name__ == "__main__":
    unittest.main()
