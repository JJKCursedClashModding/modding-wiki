import { blueprintHref, blueprints, categoryNames, enumHref, enums, fieldAnchor, groups, hrefFor, valueAnchor } from '../data.js';
import { characterHref, characters, uniqueRowAnchor, uniqueValueAnchor } from '../characters.js';

export function GET() {
  const tables = groups.flatMap((group) => {
    const href = hrefFor(group.id);
    return [
      [group.id, categoryNames[group.category], href,
        [group.overview, group.description, group.rowStruct, ...group.variants.map((variant) => variant.name)].join(' ')],
      ...group.fields.map((field) => [
        field.name, `${group.id} · ${field.type || 'Type unknown'}`, `${href}#${fieldAnchor(field.name)}`,
        [field.nativeName, field.simple, field.technical, ...field.links.map((link) => link.table)].join(' '),
      ]),
    ];
  });
  const enumEntries = enums.flatMap((entry) => {
    const href = enumHref(entry.id);
    return [
      [entry.id, 'Enum', href, entry.overview ?? ''],
      ...entry.values.map((value) => [value.name, `${entry.id} · ${value.value}`, `${href}#${valueAnchor(value.name)}`,
        [value.simple, value.technical].join(' ')]),
    ];
  });
  const blueprintEntries = blueprints.flatMap((entry) => {
    const href = blueprintHref(entry.id);
    return [
      [entry.title, 'Data Blueprints', href, [entry.overview, entry.baseClass, ...entry.examples.map((asset) => asset.name)].join(' ')],
      ...entry.fields.map((field) => [field.name, `${entry.title} · ${field.type}`, `${href}#${fieldAnchor(field.name)}`,
        [field.simple, field.technical].join(' ')]),
    ];
  });
  const characterEntries = characters.flatMap((record) => {
    const href = characterHref(record.id);
    return [
      [record.name, `Character · ${record.id}`, href, [record.storyName, record.overview, record.technicalOverview, record.controller].join(' ')],
      ...record.rows.flatMap((row) => [
        [row.key, `${record.name} · ${row.title}`, `${href}#${uniqueRowAnchor(row.index)}`, row.overview ?? ''],
        ...row.slots.filter((slot) => slot.label).map((slot) => [
          slot.label, `${record.name} · ${row.key} [${slot.index}]`, `${href}#${uniqueValueAnchor(row.index, slot.index)}`,
          [slot.simple, slot.technical].join(' '),
        ]),
      ]),
    ];
  });
  return new Response(JSON.stringify([...tables, ...enumEntries, ...blueprintEntries, ...characterEntries]), { headers: { 'Content-Type': 'application/json' } });
}
