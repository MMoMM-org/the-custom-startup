export interface Settings {
  host: string;
  port: number;
  verbose: boolean;
}

export const DEFAULT_SETTINGS: Settings = {
  host: 'localhost',
  port: 8080,
  verbose: false,
};
