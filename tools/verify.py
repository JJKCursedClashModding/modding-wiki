"""Verify the research input, generated routes, row keys, and search targets."""

import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote, urljoin, urlsplit


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
DIST = ROOT / "dist"
STATUSES = {"verified", "observed", "unresolved"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check_reference(reference, project, line_counts):
    match = re.match(r"((?:Source|Config|Plugins|Tools|docs|status)/[^:\n]+):(\d+)(?:-(\d+))?", reference)
    if not match:
        return None
    source, first, last = match.groups()
    path = project / source
    if source.casefold() == "config/defaultcrypto.ini" or ".." in Path(source).parts:
        return reference
    if path not in line_counts:
        line_counts[path] = len(path.read_bytes().splitlines()) if path.is_file() else 0
    if not 1 <= int(first) <= int(last or first) <= line_counts[path]:
        return reference
    return None


def annotation_complete(note, required=("simple", "technical")):
    return all(isinstance(note.get(key), str) and note[key].strip() for key in required)


def field_anchor(name):
    return "field-" + name.lower().replace("[]", "-array").replace(".", "--")


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.ids = Counter()
        self.statuses = Counter()
        self.hrefs = []
        self.base = "/"
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == "id":
                self.ids[value] += 1
            if key == "class" and value.startswith("badge "):
                self.statuses[value.split()[1]] += 1
            if tag == "a" and key == "href":
                self.hrefs.append(value)
            if tag == "body" and key == "data-base":
                self.base = value


def reference_documents(groups, errors, project, line_counts, strict):
    def verify_evidence(label, evidence):
        if not isinstance(evidence, list) or not evidence or not all(isinstance(ref, str) and ref.strip() for ref in evidence):
            errors.append(f"{label}: missing evidence")
            return
        if project:
            for ref in evidence:
                if check_reference(ref, project, line_counts):
                    errors.append(f"{label}: reference outside local source {ref}")

    schemas = read(CONTENT / "enums.json") | read(CONTENT / "engine-enums.json")
    enum_files = {path.stem: path for path in (CONTENT / "enum-research").glob("*.json")}
    for id in enum_files.keys() - schemas.keys():
        errors.append(f"Unexpected enum research file {id}")
    for id, schema in schemas.items():
        if id not in enum_files:
            if strict:
                errors.append(f"{id}: missing enum research")
            continue
        document = read(enum_files[id])
        values = document.get("values", {})
        declared = {name for name, _ in schema["values"]}
        if not annotation_complete(document, ("overview",)) or declared != values.keys():
            errors.append(f"{id}: missing overview or mismatch with declared enum values")
        for name, note in values.items():
            if not annotation_complete(note) or note.get("status") not in STATUSES:
                errors.append(f"{id}.{name}: incomplete enum explanation")
            verify_evidence(f"{id}.{name}", note.get("evidence"))

    links = read(CONTENT / "table-links.json")
    for id, fields in links.items():
        if id not in groups:
            errors.append(f"Unknown source table {id}")
            continue
        known = {field["name"].casefold() for field in groups[id]["fields"]}
        if len({name.casefold() for name in fields}) != len(fields):
            errors.append(f"{id}: duplicate source table fields")
        for name, targets in fields.items():
            if name.casefold() not in known or not targets:
                errors.append(f"{id}.{name}: unknown source field or no targets")
            seen = set()
            for target in targets:
                table = target.get("table")
                if table not in groups or table in seen:
                    errors.append(f"{id}.{name}: invalid target table {table}")
                seen.add(table)
                verify_evidence(f"{id}.{name} -> {table}", target.get("evidence"))

    blueprint_catalog = read(CONTENT / "data-blueprints.json")
    blueprints = blueprint_catalog["entries"]
    if strict and (not blueprints or not links):
        errors.append("Blueprint or DataTable cross-reference coverage is empty")
    seen = set()
    for entry in blueprints:
        id = entry["id"]
        if id in seen or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", id):
            errors.append(f"Invalid Blueprint slug {id}")
        seen.add(id)
        if entry.get("kind") not in {"settings", "actor"} or not annotation_complete(entry, ("title", "overview", "description", "baseClass")):
            errors.append(f"{id}: incomplete Blueprint family")
        verify_evidence(id, entry.get("evidence"))
        for field in entry["fields"]:
            if not annotation_complete(field, ("name", "type", "simple", "technical")):
                errors.append(f"{id}.{field.get('name')}: incomplete Blueprint setting")
            verify_evidence(f"{id}.{field.get('name')}", field.get("evidence"))
        for asset in entry["examples"]:
            if not annotation_complete(asset, ("name", "path", "detail")):
                errors.append(f"{id}: incomplete Blueprint example")
        for table in entry["tables"]:
            if table not in groups:
                errors.append(f"{id}: unknown Blueprint-related table {table}")

    return schemas, links, blueprints


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Require every group and field to have a review")
    parser.add_argument("--project", type=Path, help="Also verify line references against the Unreal checkout")
    args = parser.parse_args()
    catalog = read(CONTENT / "catalog.json")
    groups = {group["id"]: group for group in catalog}
    counts = Counter()
    warnings = []
    errors = []
    line_counts = {}
    for path in sorted((CONTENT / "research").glob("*.json")):
        if path.stem not in groups:
            errors.append(f"Unexpected research file {path.name}")
            continue
        try:
            article = read(path)
        except ValueError as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        counts["groups reviewed"] += bool(article.get("description"))
        overview = article.get("overview")
        counts["plain-language overviews"] += isinstance(overview, str) and bool(overview.strip())
        fields = {field["name"].casefold(): field for field in groups[path.stem]["fields"]}
        for name, note in article.get("fields", {}).items():
            if name.casefold() not in fields:
                warnings.append(f"{path.stem}: unmatched field {name}")
                continue
            status = note.get("status")
            if status not in STATUSES or not annotation_complete(note):
                errors.append(f"{path.stem}.{name}: incomplete field annotation")
                continue
            if status == "verified" and not note.get("evidence"):
                errors.append(f"{path.stem}.{name}: missing evidence for verified status")
            if args.project:
                for reference in note.get("evidence", []):
                    invalid = check_reference(reference, args.project, line_counts)
                    if invalid:
                        warnings.append(f"{path.stem}.{name}: reference outside local source {invalid}")
            counts[status] += 1

    schemas, links, blueprints = reference_documents(groups, errors, args.project, line_counts, args.strict)
    pages = {}

    def verify_page(route, anchors=()):
        path = DIST / route / "index.html"
        if not path.is_file():
            errors.append(f"/{route}: built page missing")
            return
        page = Page(path)
        pages[route] = page
        duplicates = [key for key, count in page.ids.items() if count > 1]
        if duplicates:
            errors.append(f"/{route}: duplicate anchors {duplicates}")
        for anchor in anchors:
            if anchor not in page.ids:
                errors.append(f"/{route}: missing anchor {anchor}")

    for route in ("", "tables", "enums", "data-blueprints"):
        verify_page(route)
    for group in catalog:
        slug = group["id"].lower()
        keys = read(ROOT / "public" / "row-keys" / f"{slug}.json")
        actual = Counter(index for _, indices in keys for index in indices)
        expected = Counter({i: asset["rows"] for i, asset in enumerate(group["variants"])})
        if len(keys) != group["rowKeyCount"] or actual != expected:
            errors.append(f"{slug}: row key index differs from catalog")
        verify_page(f"tables/{slug}", (field_anchor(field["name"]) for field in group["fields"]))
    for id, schema in schemas.items():
        verify_page(f"enums/{id.lower()}", (f"value-{name.lower()}" for name, _ in schema["values"]))
    for entry in blueprints:
        verify_page(f"data-blueprints/{entry['id']}", (field_anchor(field["name"]) for field in entry["fields"]))

    base = pages[""].base if "" in pages else "/"

    def check_target(href, route):
        parsed = urlsplit(urljoin(f"{base}{route}/" if route else base, href))
        if parsed.scheme or parsed.netloc:
            return True
        if not parsed.path.startswith(base):
            return False
        page = pages.get(parsed.path[len(base):].strip("/"))
        return page is not None and (not parsed.fragment or unquote(parsed.fragment) in page.ids)

    for route, page in pages.items():
        for href in set(page.hrefs):
            if not check_target(href, route):
                errors.append(f"/{route}: invalid link {href}")

    index = read(DIST / "search-index.json")
    search_targets = set()
    for _, _, href, _ in index:
        if href in search_targets or not check_target(href, ""):
            errors.append(f"Invalid or duplicate search target {href}")
        search_targets.add(href)
    total_fields = sum(len(group["fields"]) for group in catalog)
    total_values = sum(len(schema["values"]) for schema in schemas.values())
    blueprint_fields = sum(len(entry["fields"]) for entry in blueprints)
    if len(index) != len(catalog) + total_fields + len(schemas) + total_values + len(blueprints) + blueprint_fields:
        errors.append("Search index count differs from the reference catalog")

    rendered = sum((page.statuses for route, page in pages.items() if route.startswith("tables/")), Counter())
    reviewed = sum(rendered[status] for status in STATUSES)
    link_count = sum(len(targets) for fields in links.values() for targets in fields.values())
    print(f"{len(pages)} pages, {len(index)} search targets, {link_count} DataTable references")
    print(f"{len(schemas)} enums with {total_values} values, {len(blueprints)} Blueprint families with {blueprint_fields} settings")
    print(f"{counts['groups reviewed']}/{len(catalog)} group descriptions, {reviewed}/{total_fields} reviewed fields "
          f"({rendered['verified']} traced, {rendered['observed']} observed, {rendered['unresolved']} unresolved)")
    if args.strict and (counts["groups reviewed"] < len(catalog) or reviewed < total_fields):
        errors.append("Research coverage is incomplete")
    if args.strict and counts["plain-language overviews"] < len(catalog):
        errors.append("Each table needs a plain-language overview")
    for warning in warnings:
        print(f"Note: {warning}")
    for error in errors:
        print(f"Error: {error}")
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
