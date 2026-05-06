/**
 * Settings for the plugin.
 */
export interface Settings {
  /** The hostname of the server to connect to. */
  host: string;

  /** Port number to listen on. */
  port: number = 3000;

  /** Whether to enable verbose logging. */
  verbose: boolean = false;

  /** Maximum number of retries on failure. */
  maxRetries: number;

  /** No JSDoc on this one. */
  timeout: number = 30;
}
