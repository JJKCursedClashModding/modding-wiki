import catalog from '../content/catalog.json';
import enums from '../content/enums.json';

const research = import.meta.glob('../content/research/*.json', {
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
export const hrefFor = (id) => `${import.meta.env.BASE_URL}tables/${slugFor(id)}/`;

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
  const raw = research[`../content/research/${entry.id}.json`];
  let article = {};
  if (raw) {
    try {
      article = JSON.parse(raw.replace(/^\uFEFF/, ''));
    } catch (error) {
      const message = `Invalid research JSON for ${entry.id}: ${error.message}`;
      if (!import.meta.env.DEV) throw new Error(message);
      console.warn(message);
    }
  }
  const annotations = new Map(Object.entries(article.fields ?? {}).map(([key, item]) => [key.toLowerCase(), item]));
  const fields = entry.fields.map((field) => {
    let annotation = annotations.get(field.name.toLowerCase());
    if (!annotation && field.componentOf) {
      const [container, component] = field.name.split('.');
      const parent = annotations.get(container.replace(/\[\]$/, '').toLowerCase());
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
    const enumName = type.match(/\bE\w+\b/)?.[0];
    return {
      ...field,
      ...annotation,
      type,
      enum: enums[enumName],
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

export const categories = Object.entries(categoryNames).map(([id, label]) => ({
  id, label, groups: groups.filter((group) => group.category === id),
})).filter((category) => category.groups.length);
