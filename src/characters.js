import roster from '../content/characters.json';
import { readResearch, slugFor } from './data.js';

const research = import.meta.glob('../content/character-research/*.json', {
  eager: true,
  query: '?raw',
  import: 'default',
});

export const characterHref = (id) => `${import.meta.env.BASE_URL}characters/${slugFor(id)}/`;
export const uniqueRowAnchor = (index) => `unique-${index}`;
export const uniqueValueAnchor = (row, slot) => `${uniqueRowAnchor(row)}-value-${slot}`;

export const characters = roster.map((record) => {
  const article = readResearch(research, `../content/character-research/${record.id}.json`);
  const rows = record.rows.flatMap((row, index) => {
    if (!row) return [];
    const detail = article.rows?.[row.key];
    return [{
      ...row,
      index,
      title: detail?.title ?? row.key,
      overview: detail?.overview,
      notes: detail?.notes ?? [],
      slots: row.values.map((value, slot) => ({ ...detail?.values?.[slot], value, index: slot })),
    }];
  });
  return {
    ...record,
    rows,
    rowCount: record.rows.length,
    emptySlots: record.rows.flatMap((row, index) => row ? [] : [index]),
    overview: article.overview,
    technicalOverview: article.technicalOverview,
    notes: article.notes ?? [],
  };
}).sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));

export const charactersById = new Map(characters.map((record) => [record.id, record]));
export const characterRowOwners = new Map();
for (const character of characters) {
  for (const row of character.rows) {
    if (!characterRowOwners.has(row.key)) characterRowOwners.set(row.key, []);
    characterRowOwners.get(row.key).push({ id: character.id, name: character.name, index: row.index });
  }
}
