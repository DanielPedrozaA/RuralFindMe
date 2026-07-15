export const EASE_STANDARD = [0.22, 1, 0.36, 1] as const;

export const ASSIGNED_REVEAL_DELAYS = [600, 1500, 2400, 3200] as const;

// Keep the preparation screen visible through the final card reveal, with a
// short buffer before navigation to the result.
export const PREPARATION_MINIMUM_MS = ASSIGNED_REVEAL_DELAYS.at(-1)! + 1100;
