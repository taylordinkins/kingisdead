/** Short plain-language card descriptions (paraphrasing the card rules and the summon rule). Keyed by card id. */
export const CARD_TEXT: Readonly<Record<string, string>> = {
  "1": "Place up to 2 Scottish followers from the supply into one open region that borders a Scottish-controlled region, or that borders Moray if Moray is open. Then take any one follower from a region into your court.",
  "2": "Place up to 2 Welsh followers from the supply into one open region that borders a Welsh-controlled region, or that borders Gwynedd if Gwynedd is open. Then take any one follower from a region into your court.",
  "3": "Place up to 2 English followers from the supply into one open region that borders an English-controlled region, or that borders Essex if Essex is open. Then take any one follower from a region into your court.",
  "4": "Place one Scottish, one Welsh and one English follower from the supply, each into any open region. Then take any one follower from a region into your court.",
  "5": "Swap two face-up region cards that have no negotiation disc, then put your negotiation disc on one of them (the disc is then spent). Then take any one follower from a region into your court.",
  "6": "Swap one follower in one region with one follower in a different region. You may not simply undo the previous Manoeuvre. Then take any one follower from a region into your court.",
  "7": "Swap one follower in a region for two followers in a bordering region; only if that is impossible, swap one for one. You may not undo the previous Outmanoeuvre. Then take any one follower from a region into your court.",
};

export function cardText(id: string | number | null | undefined): string | undefined {
  return id == null ? undefined : CARD_TEXT[String(id)];
}
