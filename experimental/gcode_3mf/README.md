# Experimental sliced G-code 3MF / IFS preflight

This directory is a lab-only prototype on branch
`feature/gcode-3mf-ifs-preflight`.

It is intentionally isolated from the release line
`release/standalone-0.6.x`. Nothing here is installed by the normal
v0.6.x lifecycle unless a later change explicitly wires it in.

## `inspect.py`

`inspect.py` is a stdlib-only inspector for sliced `.3mf` / `.gcode.3mf`
containers used by OrcaSlicer and stock Flashforge print files.

Read-only mode:

```sh
python3 inspect.py /usr/data/gcodes/3DBenchy_PLA.3mf
```

Optional selected-plate cache extraction:

```sh
python3 inspect.py /usr/data/gcodes/3DBenchy_PLA.3mf \
  --extract-cache /usr/data/gcodes/.zmod/gcode_3mf
```

The extractor:

- requires `Metadata/plate_N.gcode` to classify a container as sliced;
- supports explicit `--plate N`;
- verifies `Metadata/plate_N.gcode.md5` when present;
- never calls `ZipFile.extract()` and rejects unsafe ZIP member names;
- bounds entry count, total uncompressed size, and selected G-code size;
- writes a cache file only when `--extract-cache` is supplied;
- writes through a temporary file and atomically renames it after checksum
  validation;
- reads `slice_info.config`, `plate_N.json`,
  `project_settings.config`, and `filament_sequence.json`;
- maps the sliced plate's one-based filament IDs onto the configured
  material arrays for later optional IFS/Spoolman preflight.

This is only the parser/cache proof. Native upload/list/print support still
belongs in the Moonraker/Fluidd side; IFS consumption of the material metadata
must remain optional.
