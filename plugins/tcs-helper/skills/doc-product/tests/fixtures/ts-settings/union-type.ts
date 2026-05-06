export interface Settings {
  /** The log level for the application. */
  logLevel: string | number;

  /** Connection mode. */
  mode: 'small' | 'medium' | 'large';

  /** Threshold value. */
  threshold: number | null;
}

export const DEFAULT_SETTINGS: Settings = {
  logLevel: 'info',
  mode: 'medium',
  threshold: 0,
};
