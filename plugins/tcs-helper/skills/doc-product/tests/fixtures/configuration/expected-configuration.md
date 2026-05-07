# Configuration

This page documents every configuration setting available in the plugin. Each row
describes a single field: its name, expected type, default value, and what it controls.
Fields marked `[NEEDS DESCRIPTION]` or `[NEEDS REVIEW]` require author attention before
the documentation is complete. Fields marked `[NEEDS DEFAULT]` have no recorded default
and should be confirmed against the source code.

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `apiKey` | `string` | `''` | The API key used to authenticate requests to the remote service. |
| `timeout` | `number` | `[NEEDS DEFAULT]` | [NEEDS DESCRIPTION] |
| `retryPolicy` | `[NEEDS REVIEW]` | `'exponential'` | The retry strategy applied on transient failures. |
| `logLevel` | `'debug' \| 'info' \| 'warn' \| 'error'` | `'info'` | Controls the verbosity of log output. |
