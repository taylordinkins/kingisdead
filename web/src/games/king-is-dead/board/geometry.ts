/**
 * Map geometry for the schematic board: one place for region shapes, centres and drawn borders.
 * Original stylised layout (not traced from any published art). Region indices follow R-001,
 * drawn borders follow R-002 adjacency exactly (checked in geometry.test.ts).
 */

export const MAP_WIDTH = 1000;
export const MAP_HEIGHT = 620;

export interface RegionShape {
  index: number;
  name: string;
  /** Polygon corners, drawn with round joins so corners look soft. */
  points: [number, number][];
  /** Label/token anchor, roughly the visual centre. */
  centre: [number, number];
  /** Terrain palette key. */
  terrain: "highland" | "moor" | "hill" | "plain" | "marsh" | "coast";
}

export const REGION_SHAPES: RegionShape[] = [
  { index: 0, name: "Moray", terrain: "highland", centre: [500, 68],
    points: [[400, 18], [600, 18], [622, 112], [378, 112]] },
  { index: 1, name: "Strathclyde", terrain: "moor", centre: [500, 178],
    points: [[372, 124], [628, 124], [668, 232], [332, 232]] },
  { index: 2, name: "Lancaster", terrain: "hill", centre: [358, 308],
    points: [[222, 244], [494, 244], [494, 372], [196, 372]] },
  { index: 3, name: "Northumbria", terrain: "moor", centre: [644, 308],
    points: [[506, 244], [790, 244], [812, 372], [506, 372]] },
  { index: 4, name: "Gwynedd", terrain: "highland", centre: [232, 446],
    points: [[94, 384], [382, 384], [352, 514], [70, 504]] },
  { index: 5, name: "Warwick", terrain: "plain", centre: [500, 442],
    points: [[394, 384], [606, 384], [632, 506], [368, 506]] },
  { index: 6, name: "Essex", terrain: "marsh", centre: [746, 446],
    points: [[618, 384], [870, 384], [848, 520], [644, 510]] },
  { index: 7, name: "Devon", terrain: "coast", centre: [500, 562],
    points: [[258, 524], [742, 524], [704, 604], [296, 604]] },
];

/** Drawn borders (roads between neighbouring regions); must equal R-002 adjacency. */
export const DRAWN_BORDERS: [number, number][] = [
  [0, 1], [1, 2], [1, 3], [2, 3], [2, 4], [2, 5], [3, 5], [3, 6],
  [4, 5], [4, 7], [5, 6], [5, 7], [6, 7],
];

export const SLOT_COUNT = 8;
