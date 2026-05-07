/**
 * Settings for the manifest-plus-source fixture.
 */
export interface PluginOptions {
  /** Sync interval in seconds. */
  syncInterval: number;

  /** Theme name to use. */
  theme: string;
}

export const DEFAULT_PLUGIN_OPTIONS: PluginOptions = {
  syncInterval: 60,
  theme: 'dark',
};
