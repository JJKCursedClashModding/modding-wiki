import catalog from '../content/catalog.json';
import enumCatalog from '../content/enums.json';
import engineEnums from '../content/engine-enums.json';
import tableLinks from '../content/table-links.json';
import blueprintCatalog from '../content/data-blueprints.json';

const research = import.meta.glob('../content/research/*.json', {
  eager: true,
  query: '?raw',
  import: 'default',
});
const enumResearch = import.meta.glob('../content/enum-research/*.json', {
  eager: true,
  query: '?raw',
  import: 'default',
});

export const categoryNames = {
  action: 'Action & movement', combat: 'Combat', character: 'Characters',
  'battle-ui': 'Battle UI & commands', audio: 'Audio & voice',
  'effects-camera': 'Effects & camera', gameplay: 'Gameplay & globals',
  world: 'World & maps', 'pve-arcade': 'PvE & arcade', story: 'Story & missions',
  'rewards-economy': 'Rewards & items', localization: 'Localization', other: 'Other tables',
};

export const slugFor = (id) => id.toLowerCase();
export const fieldAnchor = (name) => 'field-' + name.toLowerCase().replaceAll('[]', '-array').replaceAll('.', '--');
export const fieldParentName = (name) => name.slice(0, name.lastIndexOf('.')).replace(/\[\]$/, '').toLowerCase();
export const hrefFor = (id) => `${import.meta.env.BASE_URL}tables/${slugFor(id)}/`;
export const enumHref = (id) => `${import.meta.env.BASE_URL}enums/${slugFor(id)}/`;
export const valueAnchor = (name) => `value-${name.toLowerCase()}`;
export const blueprintHref = (id) => `${import.meta.env.BASE_URL}data-blueprints/${id}/`;

export const referenceSections = [
  { id: 'tables', label: 'DataTables', description: 'Settings that control combat, characters, missions, and more.' },
  { id: 'enums', label: 'Enums', description: 'What each named choice means and where the game uses it.' },
  { id: 'data-blueprints', label: 'Data Blueprints', description: 'Blueprint assets that supply settings and defaults to the game.' },
];

function readResearch(files, path) {
  const raw = files[path];
  if (!raw) return {};
  try {
    return JSON.parse(raw.replace(/^\uFEFF/, ''));
  } catch (error) {
    const message = `Invalid research JSON in ${path}: ${error.message}`;
    if (!import.meta.env.DEV) throw new Error(message, { cause: error });
    console.warn(message);
    return {};
  }
}

export const enums = Object.entries({ ...enumCatalog, ...engineEnums }).map(([id, schema]) => {
  const article = readResearch(enumResearch, `../content/enum-research/${id}.json`);
  return {
    ...schema,
    id,
    overview: article.overview,
    notes: article.notes ?? [],
    values: schema.values.map(([name, value]) => ({ ...article.values?.[name], name, value })),
    usedBy: [],
  };
}).sort((a, b) => a.id.localeCompare(b.id));

const enumsByName = new Map(enums.map((entry) => [entry.id, entry]));
export const blueprints = blueprintCatalog.entries;
export const blueprintOverview = blueprintCatalog.overview;
export const blueprintNotes = blueprintCatalog.notes;

const exportTypes = {
  str: 'JSON string', int: 'JSON integer', float: 'JSON number',
  bool: 'JSON boolean', array: 'JSON array', object: 'JSON object', NoneType: 'JSON null',
};

const componentExplanations = {
  R: 'The amount of red in this color.',
  G: 'The amount of green in this color.',
  B: 'The amount of blue in this color.',
  A: 'The part of the color that can control how see-through it looks.',
  Pitch: 'Controls up-or-down tilt.',
  Yaw: 'Controls left-or-right turning.',
  Roll: 'Controls sideways tilt.',
};

export const groups = catalog.map((entry) => {
  const article = readResearch(research, `../content/research/${entry.id}.json`);
  const annotations = new Map(Object.entries(article.fields ?? {}).map(([key, item]) => [key.toLowerCase(), item]));
  const links = new Map(Object.entries(tableLinks[entry.id] ?? {}).map(([name, targets]) => [name.toLowerCase(), targets]));
  const fields = entry.fields.map((field) => {
    let annotation = annotations.get(field.name.toLowerCase());
    if (!annotation && field.componentOf) {
      const [container, component] = field.name.split('.');
      const parent = annotations.get(fieldParentName(field.name));
      if (field.exportOnly) {
        annotation = {
          simple: ['A short text code for this color in the exported file.', parent?.simple].filter(Boolean).join(' '),
          technical: 'The export exposes Hex alongside the four native FLinearColor channels. The Unreal row declares the color struct and has no separate Hex property.',
          status: 'observed',
        };
      } else if (parent) {
        annotation = {
          simple: `${componentExplanations[component] ?? `The ${component} value for this setting.`} ${parent.simple}`,
          technical: `Stored as part of ${field.componentOf}. ${parent.technical ?? parent.simple ?? ''}`.trim(),
          evidence: parent.evidence,
          status: parent.status === 'unresolved' ? 'unresolved' : 'observed',
        };
      }
    }
    const type = field.type ?? annotation?.type ?? field.exportKinds.map((kind) => exportTypes[kind] ?? kind).join(' | ');
    const enumType = enumsByName.get(type.match(/\bE\w+\b/)?.[0]);
    enumType?.usedBy.push({ table: entry.id, field: field.name });
    return {
      ...field,
      ...annotation,
      type,
      enumId: enumType?.id,
      links: links.get(field.name.toLowerCase()) ?? [],
      status: annotation?.status ?? 'pending',
    };
  });
  return {
    ...entry,
    fields,
    description: article.description,
    overview: article.overview,
    notes: article.notes ?? [],
    usages: article.usages ?? [],
    assetRowCount: entry.variants.reduce((sum, asset) => sum + asset.rows, 0),
  };
}).sort((a, b) => a.id.localeCompare(b.id));

export const referencedBy = new Map(groups.map((group) => [group.id, []]));
for (const group of groups) {
  for (const field of group.fields) {
    for (const link of field.links) referencedBy.get(link.table)?.push({ table: group.id, field: field.name });
  }
}

export const categories = Object.entries(categoryNames).map(([id, label]) => ({
  id, label, groups: groups.filter((group) => group.category === id),
})).filter((category) => category.groups.length);
