# Hardware update probe

Temporary source-only marker used to verify the Z-Mod / Moonraker git_repo update path on a real AD5X.

Expected behavior: Update Manager pulls this commit, then Z-Mod/Moonraker executes repository update.sh, which reapplies the existing runtime transactionally without changing user configuration.
