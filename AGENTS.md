# Opel radio EEPROM tools

Keep reusable tools and generalized findings public. Keep real VINs, radio identifiers, hashes, dumps, photographs, repair history, and operation records in the locally ignored `debug/` directory. Confirm the global ignore rule with `git check-ignore -v debug/config.env` before storing private data. Never stage private files with `git add -f`.

Use `scripts/radio.py` for configured repair workflows; `scripts/eeprom_vin.py` provides the underlying image utility. Configuration comes from `RADIO_*` environment variables. Do not hard-code vehicle data or duplicate workflows in private scripts.

Preserve chip identity verification, VIN-only modifications, explicit write confirmation, and two complete readbacks. Treat an erased VIN field as experimental. Never access hardware as part of automated tests; use synthetic images and a fake programmer.

Run `uv run --no-project python -m unittest discover -s tests -v` after code changes. Before publishing, inspect staged files for private data.
