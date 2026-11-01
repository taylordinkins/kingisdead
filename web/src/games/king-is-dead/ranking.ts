/**
 * Faction ranking text per R-403. Null entries are undefined ranks: factions
 * tied on regions and recent-win (both control 0 regions) have no defined order.
 */
export function rankingText(
  ranking: readonly (number | null)[],
  name: (f: number | null) => string,
): string {
  const defined: string[] = [];
  for (const f of ranking) {
    if (f === null) break;
    defined.push(name(f));
  }
  const text = defined.join(" > ");
  if (defined.length === ranking.length) return text;
  const undef = ranking.length - defined.length;
  const ranks = Array.from({ length: undef }, (_, i) => defined.length + i + 1);
  const rankText =
    ranks.length > 1 ? `${ranks.slice(0, -1).join(", ")} and ${ranks[ranks.length - 1]}` : `${ranks[0]}`;
  return `${text}; rank${undef > 1 ? "s" : ""} ${rankText} undefined (tied factions control no regions)`;
}
