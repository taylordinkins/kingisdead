import setupBasic from "./examples/setup_basic.json";
import coronation from "./examples/coronation_tiebreak.json";
import undoBlock from "./examples/undo_block_outmanoeuvre.json";

/** Built-in examples, copied from tests/scenarios. */
export const EXAMPLES: { name: string; json: unknown }[] = [
  { name: "Basic 2-player setup", json: setupBasic },
  { name: "Coronation tiebreak (state)", json: coronation },
  { name: "Blocked Outmanoeuvre swap (state)", json: undoBlock },
];
