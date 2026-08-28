# Hardware update probe

Temporary source-only marker used to verify the Z-Mod / Moonraker git_repo update path on a real AD5X.

Expected behavior: Update Manager pulls this commit, then Z-Mod/Moonraker executes repository update.sh, which reapplies the existing runtime transactionally without changing user configuration.

Second probe: verifies the same end-to-end path after repairing the BEGIN marker accidentally removed by manual Calibration Center cleanup during hardware acceptance.
