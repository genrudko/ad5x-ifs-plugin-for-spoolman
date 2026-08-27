# Native Fluidd integration

This directory builds a native Fluidd dashboard card for the standalone AD5X IFS Plugin for Spoolman without distributing a separate Fluidd fork to users.

## Model

1. Use the exact published release tag from `ghzserg/fluidd`.
2. Apply the small fail-closed overlay from this directory.
3. Run Fluidd type-check and production build.
4. Preserve the upstream Fluidd version and `release_info.json` identity.
5. Add `ad5x_ifs_native.json` to the built distribution with the exact upstream tag, commit and IFS UI patch revision.
6. Package the resulting `dist/` as `fluidd.zip`.

The installed UI therefore remains the corresponding Sergey Fluidd release with a native IFS component added at build time. The standalone plugin backend remains independent and continues to listen on port `7913`.

## Upstream compatibility

`apply_overlay.py` deliberately uses exact source anchors. If a future Sergey Fluidd release changes one of the integration points, the build fails instead of publishing an unknown or partially patched UI.

Current native changes are intentionally limited to:

- one new Vue dashboard component;
- one Fluidd Dashboard import/registration;
- one dashboard layout entry;
- RU/EN strings.

No IFS backend, Z-Mod runtime or Moonraker code is copied into Fluidd.

The first hardware/UI acceptance target is Sergey Fluidd `v1.37.4` (`7f024c08aac4093aa8aa2e26e329df5832ebe778`).

## Automation

`.github/workflows/native-fluidd.yml` checks the latest `ghzserg/fluidd` release once per day at `03:17 UTC`, with a manual trigger available as well. Feature-branch pushes build and upload a CI artifact only. Main-branch scheduled/manual runs may publish a compatibility release after all checks pass.
