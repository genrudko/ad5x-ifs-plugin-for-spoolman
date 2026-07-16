# Fluidd integration

The plugin injects two local JavaScript assets into Fluidd's `index.html`:

- `ifs-spoolman-card-v10.js`
- `ifs-spoolman-layout-v2.js`

The card displays the active IFS slot, assigned spool and synchronization state. It also opens the standalone management interface.

The layout script provides placement controls for the card and stores layout preferences in the browser's local storage.

The installer removes older `ifs-spoolman-card*.js` and `ifs-spoolman-layout*.js` files. `uninstall_fluidd_card.sh` removes both script tags and assets.

Z-Mod or Fluidd updates may replace `index.html`. `boot_start.sh` reapplies the integration when the plugin starts.
