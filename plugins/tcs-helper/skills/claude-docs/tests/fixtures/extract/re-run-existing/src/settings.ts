/**
 * Updated settings — the docs/ page is stale relative to this.
 */
export interface RerunSettings {
  /** Host to connect to. */
  host: string;

  /** Port number. */
  port: number;

  /** Enable TLS. */
  tls: boolean;
}

export const DEFAULT_RERUN_SETTINGS: RerunSettings = {
  host: 'localhost',
  port: 3000,
  tls: false,
};
