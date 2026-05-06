/**
 * User-facing settings for the plugin.
 */
export interface Settings {
  /** API key for authentication. */
  apiKey: string;

  /** Request timeout in milliseconds. */
  requestTimeout: number = 5000;
}

/**
 * Internal runtime state — not user-facing.
 */
export interface InternalState {
  /** Whether the plugin has been initialised. */
  initialised: boolean;

  /** Current connection count. */
  connectionCount: number;
}
