"""Build the portable schema catalog from DataTable exports and Unreal declarations."""

import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
LOCALE = re.compile(r"_(De|En|Es|Es_LA|Fr|It|Ja|Ko|Pt|Zh_Hans|Zh_Hant)$")
SHARD = re.compile(r"(?<=DataTable)\d+$")
PROPERTY = re.compile(
    r"\bUPROPERTY\s*\((?:[^()]|\([^()]*\))*\)\s*"
    r"([^;{}=]+?)\s+(\w+)\s*(\[\s*\d+\s*\])?\s*(?:=[^;]*)?;",
    re.MULTILINE,
)
STRUCT = re.compile(r"\bstruct\s+(?:\w+_API\s+)?(F\w+)\b")
ENUM = re.compile(r"\benum\s+class\s+(\w+)\s*(?::\s*(\w+)\s*)?\{([^{}]*)\}", re.DOTALL)
ENUM_VALUE = re.compile(r"^(\w+)(?:\s*=\s*(-?(?:0x[0-9A-Fa-f]+|\d+)))?(?:\s+UMETA\(.*\))?$", re.DOTALL)
ENGINE_MEMBERS = {
    "FVector": dict.fromkeys("XYZ", "double"),
    "FVector4": dict.fromkeys("XYZW", "double"),
    "FRotator": dict.fromkeys(("Pitch", "Yaw", "Roll"), "double"),
    "FLinearColor": dict.fromkeys("RGBA", "float"),
}
NATIVE_TABLES = {
    "DebugTextTable": ("DataTableRow_DebugText", "Framework", "localization"),
    "GameWidgetInputGuideControllerImageRow": ("GameWidgetInputGuideControllerImageRow", "Abrams", "battle-ui"),
    "GameWidgetInputGuideKeyboardImageRow": ("GameWidgetInputGuideKeyboardImageRow", "Abrams", "battle-ui"),
    "GameWidgetRichTextBlockImageRow": ("GameWidgetRichTextBlockImageRow", "Abrams", "battle-ui"),
}


def read(path):
    return path.read_text(encoding="utf-8-sig", errors="replace")


def group_name(name, stem):
    if stem in {"GameDataTableRow_GameText", "GameDataTableRow_SystemText"}:
        name = LOCALE.sub("", name)
    return SHARD.sub("", name)


def observed_fields(values, fields, prefix=""):
    for key, value in values.items():
        name = prefix + key
        kinds = fields.setdefault(name, set())
        if isinstance(value, dict):
            kinds.add("object")
            observed_fields(value, fields, name + ".")
        elif isinstance(value, list):
            kinds.add("array")
            for item in value:
                if isinstance(item, dict):
                    observed_fields(item, fields, name + "[].")
        else:
            kinds.add(type(value).__name__)


def header_index(source):
    structs = {}
    for path in source.rglob("*.h"):
        if not path.stem.startswith(("Game", "DataTable", "SystemText", "DebugText")):
            continue
        content = read(path)
        if "USTRUCT" not in content or not STRUCT.search(content):
            continue
        props = {}
        for match in PROPERTY.finditer(content):
            field_type, key, extent = match.groups()
            props[key] = {
                "type": " ".join(field_type.split()) + (extent.replace(" ", "") if extent else ""),
                "source": f"{path.relative_to(source.parent).as_posix()}:{content.count(chr(10), 0, match.start()) + 1}",
            }
        if props:
            structs["F" + path.stem] = props
    return structs


def enum_index(source, used_types):
    enums = {}
    for path in source.rglob("*.h"):
        if path.stem not in used_types:
            continue
        content = read(path)
        for match in ENUM.finditer(content):
            name, underlying, block = match.groups()
            if name not in used_types:
                continue
            block = re.sub(r"/\*.*?\*/|//[^\n]*", "", block, flags=re.DOTALL)
            block = re.sub(r"\bUMETA\([^()]*\)", "", block)
            names = []
            value = -1
            for item in filter(None, map(str.strip, block.split(","))):
                entry = ENUM_VALUE.fullmatch(item)
                if not entry:
                    break
                member, explicit = entry.groups()
                value = int(explicit, 0) if explicit is not None else value + 1
                names.append([member, value])
            else:
                enums[name] = {
                    "values": names,
                    "underlying": underlying,
                    "source": f"{path.relative_to(source.parent).as_posix()}:{content.count(chr(10), 0, match.start()) + 1}",
                }
    return enums


def native_field(path, stem, structs):
    current = "F" + stem
    info = {}
    key = ""
    for part in path.split("."):
        member = part.removesuffix("[]").casefold()
        candidates = structs.get(current, {})
        native = next(((key, info) for key, info in candidates.items() if key.casefold() == member), None)
        builtin = next(((key, kind) for key, kind in ENGINE_MEMBERS.get(current, {}).items()
                        if key.casefold() == member), None)
        if native:
            key, info = native
        elif builtin:
            key, kind = builtin
            info = {**info, "type": kind, "componentOf": current}
        elif current == "FLinearColor" and member == "hex":
            return {"type": "JSON string", "exportOnly": True, "componentOf": current}
        else:
            return None
        current = info["type"].removeprefix("TArray<").removesuffix(">")
    return {"nativeName": key, **info}


def load_exports(export_dir, wiki_dir):
    categories = {path.stem: path.parent.name for path in wiki_dir.glob("*/*.md")
                  if path.name != "README.md"}
    groups = {}
    for path in sorted(export_dir.glob("*.json")):
        for table in json.loads(read(path)):
            if table.get("Type") != "DataTable" or "Rows" not in table:
                continue
            properties = table["Properties"]
            struct = properties["RowStruct"]
            stem = struct["ObjectName"].split("'")[1]
            name = table["Name"]
            group = group_name(name, stem)
            entry = groups.setdefault(group, {
                "id": group, "category": categories.get(group, categories.get(name, "other")),
                "rowStruct": stem, "module": struct["ObjectPath"],
                "variants": [], "observed": {}, "fieldVariants": {}, "keys": {},
            })
            if entry["rowStruct"] != stem:
                raise ValueError(f"{group} has different schemas: {entry['rowStruct']} and {stem}")
            rows = table["Rows"]
            entry["variants"].append({"name": name, "rows": len(rows),
                                      "importKey": properties.get("ImportKeyField")})
            variant_index = len(entry["variants"]) - 1
            variant_fields = {}
            for key, row in rows.items():
                entry["keys"].setdefault(key, []).append(variant_index)
                observed_fields(row, variant_fields)
            for field, kinds in variant_fields.items():
                entry["observed"].setdefault(field, set()).update(kinds)
                entry["fieldVariants"].setdefault(field, []).append(variant_index)
    return groups


def index_references(project, groups):
    by_symbol = defaultdict(set)
    accessors = defaultdict(set)
    for name, entry in groups.items():
        by_symbol[name].add(name)
        stem = entry["rowStruct"]
        by_symbol["F" + stem].add(name)
        if stem not in {"GameDataTableRow_GameText", "GameDataTableRow_SystemText"}:
            short = stem.removeprefix("GameDataTableRow_")
            for symbol in (f"Get{short}Row", f"Find{short}Row", f"Get{short}Data",
                           f"Get{short}DataTable"):
                accessors[symbol].add(name)
            by_symbol[f"{short}DataTables"].add(name)
        for variant in entry["variants"]:
            by_symbol[variant["name"]].add(name)
    pattern = re.compile(r"\b(?:" + "|".join(map(re.escape, by_symbol))
                         + r"|(?:[A-Za-z0-9]+_)*(?P<accessor>"
                         + "|".join(map(re.escape, accessors)) + r"))\b")
    refs = defaultdict(lambda: defaultdict(dict))
    roots = [project / name for name in ("Source", "Config", "Plugins")]
    files = (path for root in roots for path in sorted(root.rglob("*"))
             if path.suffix in {".cpp", ".h", ".inl", ".ini"}
             and not {"Intermediate", "Binaries", "Saved"}.intersection(path.parts)
             and path.name.casefold() != "defaultcrypto.ini")
    for path in files:
        relative = path.relative_to(project).as_posix()
        content = read(path)
        matches = list(pattern.finditer(content))
        if not matches:
            continue
        newlines = [m.start() for m in re.finditer("\n", content)]
        for match in matches:
            symbol = match.group(0)
            line = bisect_right(newlines, match.start()) + 1
            for name in (accessors[match["accessor"]] if match["accessor"] else by_symbol[symbol]):
                file_refs = refs[name][relative]
                file_refs.setdefault(symbol, []).append(line)
    return refs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--exports", type=Path, required=True, help="DataTables repository checkout")
    args = parser.parse_args()
    source = args.project / "Source"
    structs = header_index(source)
    groups = load_exports(args.exports / "datatables", args.exports / "wiki" / "datatables")
    exported_structs = {entry["rowStruct"] for entry in groups.values()}
    for name, (stem, module, category) in NATIVE_TABLES.items():
        if stem in exported_structs or "F" + stem not in structs:
            continue
        groups[name] = {
            "id": name, "category": category, "rowStruct": stem, "module": f"/Script/{module}",
            "variants": [], "observed": {}, "fieldVariants": {}, "keys": {},
        }
    refs = index_references(args.project, groups)
    key_data = ROOT / "public" / "row-keys"
    key_data.mkdir(parents=True, exist_ok=True)
    for name, entry in sorted(groups.items()):
        stem = entry["rowStruct"]
        fields = entry.pop("observed")
        field_variants = entry.pop("fieldVariants")
        present = {field.casefold() for field in fields}
        for native in structs.get("F" + stem, {}):
            if native.casefold() not in present:
                fields[native] = set()
        entry["fields"] = []
        for field, kinds in sorted(fields.items(), key=lambda item: item[0].casefold()):
            entry["fields"].append({"name": field, "exportKinds": sorted(kinds),
                                    "seenInVariants": len(field_variants.get(field, [])),
                                    **(native_field(field, stem, structs) or {})})
        keys = entry.pop("keys")
        counts = Counter(len(variants) for variants in keys.values())
        entry["rowKeyCount"] = len(keys)
        entry["repeatedKeys"] = sum(count for times, count in counts.items() if times > 1)
        entry["references"] = refs.get(name, {})
        (key_data / f"{name.lower()}.json").write_text(
            json.dumps(sorted(keys.items()), ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
        )
    (ROOT / "content" / "catalog.json").write_text(
        json.dumps(list(groups.values()), ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    used_types = {part for group in groups.values() for field in group["fields"]
                  for part in re.findall(r"\bE\w+\b", field.get("type", ""))}
    (ROOT / "content" / "enums.json").write_text(
        json.dumps(enum_index(source, used_types), ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    print(f"{len(groups)} groups, {sum(len(x['variants']) for x in groups.values())} exports, "
          f"{sum(len(x['fields']) for x in groups.values())} fields")


if __name__ == "__main__":
    main()
