/**
 * Settings for the multi-source fixture.
 */
export interface AppSettings {
  /** API endpoint URL. */
  apiUrl: string;

  /** Request timeout in milliseconds. */
  timeoutMs: number;
}

export const DEFAULT_APP_SETTINGS: AppSettings = {
  apiUrl: 'https://api.example.com',
  timeoutMs: 5000,
};
