# Jujutsu Kaisen CC DataTables

A static Astro reference for the Jujutsu Kaisen Cursed Clash Unreal project. The site builds one page per table family and a browser-side search index from JSON.

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

## Refresh the catalog

Use the Unreal project and the community DataTables exports as read-only inputs. The generated catalog contains schema and source references. The generated row-key indexes contain keys and variant membership.

```sh
python tools/catalog.py --project "path/to/Jujutsu Kaisen CC" --exports "path/to/JJKCCDatatables"
```

The code reference index records text matches for table names, types, and accessors. Research files describe the runtime paths and their evidence. The source snapshot and assets have gaps, so retail behavior may need additional verification.

Exports are from [JJKCursedClashModding/DataTables](https://github.com/JJKCursedClashModding/DataTables). Names and stubs are attributed to the [community UE5 Mod Kit](https://github.com/JJKCursedClashModding/UE5-Mod-Kit).
