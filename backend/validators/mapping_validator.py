from collections import defaultdict
from fastapi import HTTPException

def validate_mapping_no_duplicates(mapping: dict):
    reverse_map = defaultdict(list)

    for col, info in mapping.items():
        target = info.get("mapped_to")

        if not target or target == "unknown":
            continue

        reverse_map[target].append(col)

    conflicts = {
        target: cols
        for target, cols in reverse_map.items()
        if len(cols) > 1
    }

    if conflicts:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Duplicate mapping detected",
                "conflicts": conflicts
            }
        )


        