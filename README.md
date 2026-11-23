# Jujutsu Kaisen CC Modding Wiki

A static Astro reference for the Jujutsu Kaisen Cursed Clash Unreal project. The site builds DataTable, enum, and Data Blueprint pages from JSON and indexes them for browser-side search.

Read the [modding wiki](https://jjkcursedclashmodding.github.io/modding-wiki/). GitHub Actions builds, verifies, and publishes the site on pushes to `main`.

```sh
npm ci
npm run build
npm run verify
npm run preview
```

Use Node.js 22 or newer and Python 3.10 or newer. Astro writes the deployable site to `dist/`. The site can be served from a static host. Set `DOCS_BASE=/repository-name/` before building for a GitHub Pages project path.

## Edit a table page

Add or edit `content/research/<ExactGroupName>.json`. The name comes from `content/catalog.json`. Use the exact exported field path from the catalog for each field annotation. Field matching ignores case.

```json
{
  "overview": "One plain-English sentence about what this table changes in the game.",
  "description": "Describe what one row configures and where the table is used.",
  "fields": {
    "ExampleField": {
      "simple": "Explain what this setting does in words a player would use.",
      "technical": "Explain when the engine reads it, any boundaries, units, defaults, and important interactions.",
      "status": "verified",
      "evidence": ["Source/Module/Private/Example.cpp:42"]
    }
  },
  "usages": [
    {
      "source": "Source/Module/Private/Example.cpp:42",
      "detail": "Describe how this consumer looks up or uses the table."
    }
  ],
  "notes": ["Add caveats, variant behavior, or findings relevant to editing this table."]
}
```

Use `verified` for behavior with a traced code consumer, `observed` for a schema, loader, or data observation, and `unresolved` for a field whose behavior still lacks evidence. The catalog supplies the Unreal type. Add a `type` to an annotation when the native type is known and absent from the catalog. Fields without annotations display their review status on the page.

## Edit other reference pages and links

- `content/enum-research/<ExactEnumName>.json` has an `overview`, a `values` map keyed by exact member name, and `notes`. Each member uses the same `simple`, `technical`, `status`, and `evidence` keys as a table setting. Declaration names, numbers, and types come from `content/enums.json` and `content/engine-enums.json`.
- `content/table-links.json` maps source table names to fields. Each field holds an array of objects with a target `table`, source `evidence`, and an optional `note` for conditional lookups. The site builds the reverse links automatically.
- `content/data-blueprints.json` describes Blueprint families, example asset paths, native settings, and related DataTables. Keep package observations and consumer-traced defaults distinct.

## Refresh the catalog

Use the Unreal project and the community DataTables exports as read-only inputs. The generated catalog contains schema and source references. The generated row-key indexes contain keys and variant membership.

```sh
python tools/catalog.py --project "path/to/Jujutsu Kaisen CC" --exports "path/to/JJKCCDatatables"
```

The code reference index records text matches for table names, types, and accessors. Research files describe the runtime paths and their evidence. The source snapshot and assets have gaps, so retail behavior may need additional verification.

Exports are from [JJKCursedClashModding/DataTables](https://github.com/JJKCursedClashModding/DataTables). Names and stubs are attributed to the [community UE5 Mod Kit](https://github.com/JJKCursedClashModding/UE5-Mod-Kit).
