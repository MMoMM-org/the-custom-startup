/**
 * Settings with one field missing from the const.
 */
export interface Settings {
  /** The hostname to connect to. */
  host: string;

  /** Port number. */
  port: number;

  /** Timeout in seconds. */
  timeout?: number;
}

// Note: 'timeout' is intentionally absent from the const to exercise [NEEDS DEFAULT].
// The field is optional (?) so this const is valid TypeScript.
export const DEFAULT_SETTINGS: Settings = {
  host: 'localhost',
  port: 8080,
};
