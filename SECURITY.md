# Security policy

## Supported versions

Only the newest beta release is supported during the pre-1.0 development phase.

## Network exposure

The plugin binds to `0.0.0.0:7913` by default and the current beta API has no authentication. Use it only on a trusted local network. Do not expose port `7913` directly to the public Internet.

The plugin proxies operational requests to local Moonraker and may change the active Spoolman spool. Restrict SSH and printer-network access accordingly.

## Reporting a vulnerability

Do not publish sensitive printer/network details in a public issue. Contact the repository owner privately through their GitHub profile before public disclosure.
