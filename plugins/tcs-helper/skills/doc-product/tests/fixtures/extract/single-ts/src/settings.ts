/**
 * Settings for the extract-detection fixture.
 */
export interface PluginSettings {
  /** The plugin name. */
  name: string;

  /** Enable verbose logging. */
  verbose: boolean;
}

export const DEFAULT_PLUGIN_SETTINGS: PluginSettings = {
  name: 'my-plugin',
  verbose: false,
};
