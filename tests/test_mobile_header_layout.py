from pathlib import Path

component = Path("native-fluidd/overlay/src/components/widgets/ad5x-ifs/Ad5xIfsCard.vue").read_text(encoding="utf-8")

checks = {
    "custom title slot keeps collapse control in CollapsableCard's dedicated column": '<template #title>' in component,
    "mobile action row exists": 'ifs-header-actions--mobile' in component,
    "desktop action row exists": 'ifs-header-actions--desktop' in component,
    "mobile actions use compact controls": 'ifs-header-actions--mobile' in component and 'x-small' in component,
    "mobile breakpoint defines responsive header": '@media (max-width: 600px)' in component and '.ifs-card-title' in component,
}

failed = [message for message, ok in checks.items() if not ok]
if failed:
    raise SystemExit("Mobile IFS header regression:\n- " + "\n- ".join(failed))
