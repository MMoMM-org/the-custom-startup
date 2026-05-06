/**
 * Settings interface with no matching DEFAULT_* const.
 * All defaults should be [NEEDS DEFAULT].
 */
export interface Settings {
  /** The server host. */
  host: string;

  /** The server port. */
  port: number;

  /** Enable debug logging. */
  debug: boolean;
}
