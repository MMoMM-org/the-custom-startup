/**
 * Settings for the plugin.
 */
export interface Settings {
  /** Description for foo. */
  foo: string;

  /** Description for bar. */
  bar: number;
}

export const DEFAULT_SETTINGS: Settings = {
  foo: 'hello',
  bar: 5,
};
