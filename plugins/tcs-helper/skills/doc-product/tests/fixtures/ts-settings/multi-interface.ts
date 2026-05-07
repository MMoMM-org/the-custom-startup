/**
 * User-facing settings for the plugin.
 */
export interface Settings {
  /** API key for authentication. */
  apiKey: string;

  /** Request timeout in milliseconds. */
  requestTimeout: number;
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

export const DEFAULT_SETTINGS: Settings = {
  apiKey: '',
  requestTimeout: 5000,
};

export const DEFAULT_INTERNAL_STATE: InternalState = {
  initialised: false,
  connectionCount: 0,
};
