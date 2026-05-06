export interface Settings {
  /** Simple string field — should parse fine. */
  name: string;

  /** Field with generic type — needs review. */
  cache: Map<string, number>;

  /** Field with mapped type — needs review. */
  overrides: { [K in string]: boolean };

  /** Field with intersection type — needs review. */
  config: BaseConfig & ExtendedConfig;

  /** Field with array generic — needs review. */
  tags: Array<string>;

  /** Plain array is ok. */
  labels: string[];
}
