import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import eeprom_vin as vin
import radio
from test_eeprom_vin import synthetic_image


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = synthetic_image()
        self.target_vin = "W11111111B7654321"
        self.target = vin.build_modified(self.source, vin.DEFAULT_OFFSET, vin.encode_vin(self.target_vin))
        self.donor = self.root / "donor.bin"
        self.original = self.root / "original.bin"
        self.chip = self.root / "chip.bin"
        self.target_path = self.root / "target.bin"
        self.calls = self.root / "calls.txt"
        self.donor.write_bytes(self.source)
        self.original.write_bytes(self.target)
        self.chip.write_bytes(self.source)
        self.target_path.write_bytes(self.target)
        self.programmer = self.root / "programmer"
        self.programmer.write_text(f"""#!{sys.executable}
import os, sys
from pathlib import Path
args = sys.argv[1:]
chip = Path(os.environ['FAKE_CHIP'])
calls = Path(os.environ['FAKE_CALLS'])
with calls.open('a') as out:
    out.write(('write' if '-w' in args else 'read') + '\\n')
if '-w' in args:
    chip.write_bytes(Path(args[args.index('-w') + 1]).read_bytes())
else:
    data = chip.read_bytes()
    if os.environ.get('FAKE_BAD_READ'):
        data = bytes([0]) * len(data)
    if os.environ.get('FAKE_BAD_POSTWRITE') and 'write' in calls.read_text():
        data = data[:-1] + bytes([data[-1] ^ 1])
    Path(args[args.index('-r') + 1]).write_bytes(data)
""")
        self.programmer.chmod(0o755)
        env = {
            "RADIO_DATA_DIR": str(self.root / "data"),
            "RADIO_PROGRAMMER": str(self.programmer),
            "RADIO_TARGET_VIN": self.target_vin,
            "RADIO_DONOR_IMAGE": str(self.donor),
            "RADIO_DONOR_SHA256": vin.sha256(self.source),
            "RADIO_ORIGINAL_IMAGE": str(self.original),
            "RADIO_ORIGINAL_SHA256": vin.sha256(self.target),
            "FAKE_CHIP": str(self.chip),
            "FAKE_CALLS": str(self.calls),
        }
        self.environment = patch.dict(os.environ, env)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_patch_requires_original_vin_corroboration(self):
        self.original.write_bytes(self.source)
        with patch.dict(os.environ, {"RADIO_ORIGINAL_SHA256": vin.sha256(self.source)}), self.assertRaisesRegex(ValueError, "corroborated"):
            radio.candidate("donor")

    def test_modified_backup_is_rejected_before_hardware_access(self):
        self.donor.write_bytes(self.target)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            radio.write("donor", self.target_path, False)
        self.assertFalse(self.calls.exists())

    def test_non_vin_change_is_rejected_before_hardware_access(self):
        damaged = bytearray(self.target)
        damaged[0] ^= 1
        self.target_path.write_bytes(damaged)
        with self.assertRaisesRegex(ValueError, "VIN-only"):
            radio.write("donor", self.target_path, False)
        self.assertFalse(self.calls.exists())

    def test_wrong_chip_is_never_written(self):
        different = bytearray(self.source)
        different[0] ^= 1
        self.chip.write_bytes(different)
        with patch("builtins.input", return_value="CHECK DONOR"), self.assertRaisesRegex(ValueError, "Seated chip"):
            radio.write("donor", self.target_path, False)
        self.assertEqual(self.calls.read_text(), "read\n")

    def test_cancelled_write_preserves_chip(self):
        with patch("builtins.input", side_effect=["CHECK DONOR", "NO"]), self.assertRaisesRegex(ValueError, "Cancelled"):
            radio.write("donor", self.target_path, False)
        self.assertEqual(self.chip.read_bytes(), self.source)
        self.assertEqual(self.calls.read_text(), "read\n")

    def test_write_requires_confirmation_and_two_full_readbacks(self):
        with patch("builtins.input", side_effect=["CHECK DONOR", "WRITE DONOR"]):
            radio.write("donor", self.target_path, False)
        self.assertEqual(self.chip.read_bytes(), self.target)
        self.assertEqual(self.calls.read_text(), "read\nwrite\nread\nread\n")

    def test_already_programmed_chip_is_verified_without_write(self):
        self.chip.write_bytes(self.target)
        with patch("builtins.input", return_value="CHECK DONOR"):
            radio.write("donor", self.target_path, False)
        self.assertEqual(self.calls.read_text(), "read\nread\n")

    def test_failed_postwrite_verification_is_reported(self):
        with patch.dict(os.environ, {"FAKE_BAD_POSTWRITE": "1"}), patch("builtins.input", side_effect=["CHECK DONOR", "WRITE DONOR"]), self.assertRaisesRegex(ValueError, "Post-write verification"):
            radio.write("donor", self.target_path, False)

    def test_uniform_read_is_rejected(self):
        with patch.dict(os.environ, {"FAKE_BAD_READ": "1"}), patch("builtins.input", return_value="READ DONOR"), self.assertRaisesRegex(ValueError, "uniform"):
            radio.read("donor")

    def test_three_independent_reads(self):
        with patch("builtins.input", return_value="READ DONOR"):
            radio.read("donor")
        self.assertEqual(self.calls.read_text(), "read\nread\nread\n")

    def test_clear_needs_explicit_experimental_write_mode(self):
        cleared = radio.candidate("original", True)
        self.target_path.write_bytes(cleared)
        with self.assertRaisesRegex(ValueError, "VIN-only"):
            radio.write("original", self.target_path, False)
        self.chip.write_bytes(self.target)
        with patch("builtins.input", side_effect=["CHECK ORIGINAL", "WRITE EXPERIMENTAL CLEAR ORIGINAL"]):
            radio.write("original", self.target_path, True)
        self.assertEqual(self.chip.read_bytes(), cleared)

    def test_build_is_repeatable_but_never_overwrites_other_data(self):
        radio.build("donor", False)
        radio.build("donor", False)
        output = self.root / "data/images/donor-vin.bin"
        self.assertEqual(output.read_bytes(), self.target)
        output.chmod(0o600)
        output.write_bytes(self.source)
        with self.assertRaisesRegex(ValueError, "overwrite"):
            radio.build("donor", False)


if __name__ == "__main__":
    unittest.main()
