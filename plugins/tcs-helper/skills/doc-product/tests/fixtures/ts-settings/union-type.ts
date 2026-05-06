export interface Settings {
  /** The log level for the application. */
  logLevel: string | number;

  /** Connection mode. */
  mode: "tcp" | "udp" | "ws";

  /** Threshold value. */
  threshold: number | null = 0;
}
