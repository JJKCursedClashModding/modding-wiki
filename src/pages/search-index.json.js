import { categoryNames, fieldAnchor, groups, hrefFor } from '../data.js';

export function GET() {
  const entries = groups.flatMap((group) => {
    const href = hrefFor(group.id);
    return [
      [group.id, categoryNames[group.category], href,
        [group.overview, group.description, group.rowStruct, ...group.variants.map((variant) => variant.name)].join(' ')],
      ...group.fields.map((field) => [
        field.name, `${group.id} · ${field.type || 'Type unknown'}`, `${href}#${fieldAnchor(field.name)}`,
        [field.nativeName, field.simple, field.technical].join(' '),
      ]),
    ];
  });
  return new Response(JSON.stringify(entries), { headers: { 'Content-Type': 'application/json' } });
}
