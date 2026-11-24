"""Build the character roster and ordered unique rows from the public DataTable exports."""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_rows(exports, asset):
    path = exports / f"{asset}.json"
    return json.loads(path.read_text(encoding="utf-8-sig"))[0]["Rows"]


def create_catalog(exports):
    characters = read_rows(exports, "CharacterDataTable")
    glossary = read_rows(exports, "GlossaryTextDataTable_En")
    select = read_rows(exports, "CharacterSelectDataTable")
    variants = read_rows(exports, "CharacterVariationDataTable")
    unique_rows = {}
    for number in range(1, 6):
        asset = f"CharacterUniqueDataTable{number}"
        for key, row in read_rows(exports, asset).items():
            unique_rows.setdefault(key, {"key": key, "asset": asset, "values": row["FloatValue"]})

    def display_name(key):
        return glossary.get(key, {}).get("Text")

    def present(value):
        return value if value and value != "None" else None

    catalog = []
    for id, row in sorted(characters.items()):
        name = display_name(row["Id_GlossaryText_Name"]) or id
        story_name = display_name(row["Id_GlossaryText_StoryName"])
        related = []
        for table, label in (
            ("CharacterBaseParameter", "Base stats"), ("CharacterCursedEnergy", "Cursed energy"),
            ("Action", "Action settings"), ("CommandList", "Command list"),
            ("CharacterSpecialAttack", "Special attacks"), ("CharacterTrap", "Traps"), ("CharacterShikigami", "Summons"),
        ):
            keys = row.get(f"Id_{table}", [])
            keys = keys if isinstance(keys, list) else [keys]
            active = [key for key in keys if present(key)]
            if active:
                related.append({"table": f"{table}DataTable", "label": label, "keys": active})
        unique = []
        for key in row["Id_CharacterUnique"]:
            if not present(key):
                unique.append(None)
            elif key in unique_rows:
                unique.append(unique_rows[key])
            else:
                raise ValueError(f"{id}: unresolved unique row {key}")

        catalog.append({
            "id": id,
            "name": name,
            "storyName": story_name if story_name != name else None,
            "selectable": id in select,
            "transformation": present(row["Id_Character_Transformation"]),
            "controller": row["ActionControllerType"].split("::")[-1],
            "variantCount": sum(key in variants for key in row["Id_CharacterVariation"]),
            "rows": unique,
            "related": related,
        })
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exports", type=Path, required=True, help="Directory containing the DataTable JSON files")
    args = parser.parse_args()
    catalog = create_catalog(args.exports)
    path = ROOT / "content" / "characters.json"
    path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(catalog)} character records")


if __name__ == "__main__":
    main()
