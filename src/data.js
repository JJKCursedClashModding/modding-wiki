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
          simple: `Hex representation of ${container} in the JSON export.`,
          technical: 'The export exposes Hex alongside the four native FLinearColor channels. The Unreal row declares the color struct and has no separate Hex property.',
          status: 'observed',
        };
      } else if (parent) {
        const channel = { R: 'red', G: 'green', B: 'blue', A: 'alpha' }[component];
        annotation = {
          simple: `${channel ?? component} component of ${container}.`,
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
    notes: article.notes ?? [],
    usages: article.usages ?? [],
    reviewed: fields.filter((field) => field.status !== 'pending').length,
    assetRowCount: entry.variants.reduce((sum, asset) => sum + asset.rows, 0),
  };
}).sort((a, b) => a.id.localeCompare(b.id));

export const categories = Object.entries(categoryNames).map(([id, label]) => ({
  id, label, groups: groups.filter((group) => group.category === id),
})).filter((category) => category.groups.length);
