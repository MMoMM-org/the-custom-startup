type BaseConfig = { base: string };
type ExtendedConfig = { extended: boolean };
type Foo = { id: number };
type MappedKeys = 'alpha' | 'beta';

export interface Settings {
  /** Simple string field — should parse fine. */
  name: string;

  /** Field with generic type — needs review. */
  metadata: Record<string, unknown>;

  /** Field with keyof — needs review. */
  sortKey: keyof Foo;

  /** Field with intersection type — needs review. */
  config: BaseConfig & ExtendedConfig;

  /** Field with mapped type — needs review. */
  mappedProp: { [K in MappedKeys]: string };
}

export const DEFAULT_SETTINGS: Settings = {
  name: 'default',
  metadata: {},
  sortKey: 'id',
  config: { base: '', extended: false },
  mappedProp: { alpha: 'a', beta: 'b' },
};
