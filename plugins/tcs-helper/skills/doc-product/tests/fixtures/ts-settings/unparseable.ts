type BaseConfig = { base: string };
type ExtendedConfig = { extended: boolean };
type Foo = { id: number };

export interface Settings {
  /** Simple string field — should parse fine. */
  name: string;

  /** Field with generic type — needs review. */
  metadata: Record<string, unknown>;

  /** Field with keyof — needs review. */
  sortKey: keyof Foo;

  /** Field with intersection type — needs review. */
  config: BaseConfig & ExtendedConfig;
}

export const DEFAULT_SETTINGS: Settings = {
  name: 'default',
  metadata: {},
  sortKey: 'id',
  config: { base: '', extended: false },
};
