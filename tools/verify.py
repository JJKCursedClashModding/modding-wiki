"""Verify the research input, generated routes, row keys, and search targets."""

import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check_reference(reference, project, line_counts):
    match = re.match(r"((?:Source|Config|Plugins|Tools|docs|status)/[^:\s]+):(\d+)", reference)
    if not match:
        return None
    source, line = match.groups()
    path = project / source
    if path not in line_counts:
        line_counts[path] = len(path.read_bytes().splitlines()) if path.is_file() else 0
    if not 1 <= int(line) <= line_counts[path]:
        return reference
    return None


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.ids = Counter()
        self.statuses = Counter()
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == "id":
                self.ids[value] += 1
            if key == "class" and value.startswith("badge "):
                self.statuses[value.split()[1]] += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Require every group and field to have a review")
    parser.add_argument("--project", type=Path, help="Also verify line references against the Unreal checkout")
    args = parser.parse_args()
    catalog = read(ROOT / "content" / "catalog.json")
    groups = {group["id"]: group for group in catalog}
    counts = Counter()
    warnings = []
    errors = []
    line_counts = {}
    for path in sorted((ROOT / "content" / "research").glob("*.json")):
        if path.stem not in groups:
            errors.append(f"Unexpected research file {path.name}")
            continue
        try:
            article = read(path)
        except ValueError as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        counts["groups reviewed"] += bool(article.get("description"))
        fields = {field["name"].casefold(): field for field in groups[path.stem]["fields"]}
        for name, note in article.get("fields", {}).items():
            if name.casefold() not in fields:
                warnings.append(f"{path.stem}: unmatched field {name}")
                continue
            status = note.get("status")
            if status not in {"verified", "observed", "unresolved"} or not all(
                isinstance(note.get(key), str) and note[key].strip() for key in ("simple", "technical")
            ):
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

    pages = {}
    for group in catalog:
        slug = group["id"].lower()
        keys = read(ROOT / "public" / "row-keys" / f"{slug}.json")
        actual = Counter(index for _, indices in keys for index in indices)
        expected = Counter({i: asset["rows"] for i, asset in enumerate(group["variants"])})
        if len(keys) != group["rowKeyCount"] or actual != expected:
            errors.append(f"{slug}: row key index differs from catalog")
        page = ROOT / "dist" / "tables" / slug / "index.html"
        if page.is_file():
            pages[slug] = Page(page)
            duplicates = [key for key, count in pages[slug].ids.items() if count > 1]
            if duplicates:
                errors.append(f"{slug}: duplicate anchors {duplicates}")
        else:
            errors.append(f"{slug}: built page missing")

    index = read(ROOT / "dist" / "search-index.json")
    for title, context, href, tokens in index:
        parsed = urlsplit(href)
        slug = parsed.path.strip("/").split("/")[-1]
        if slug not in pages or (parsed.fragment and parsed.fragment not in pages[slug].ids):
            errors.append(f"Invalid search target {href}")
    total_fields = sum(len(group["fields"]) for group in catalog)
    if len(index) != len(catalog) + total_fields:
        errors.append("Search index is missing groups or fields")

    rendered = sum((page.statuses for page in pages.values()), Counter())
    reviewed = sum(rendered[status] for status in ("verified", "observed", "unresolved"))
    print(f"{len(pages)}/{len(catalog)} pages, {len(index)} search targets")
    print(f"{counts['groups reviewed']}/{len(catalog)} group descriptions, {reviewed}/{total_fields} reviewed fields "
          f"({rendered['verified']} traced, {rendered['observed']} observed, {rendered['unresolved']} unresolved)")
    if args.strict and (counts["groups reviewed"] < len(catalog) or reviewed < total_fields):
        errors.append("Research coverage is incomplete")
    for warning in warnings:
        print(f"Note: {warning}")
    for error in errors:
        print(f"Error: {error}")
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
