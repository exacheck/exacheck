# ExaCheck - ExaBGP Service Health Checker

[ExaCheck](https://github.com/exacheck/exacheck) works in conjunction with [ExaBGP](https://github.com/Exa-Networks/exabgp) to health check services and announce BGP routes depending on the state of the service.

For additional information, deployment instructions and configuration examples please check the [ExaCheck website](https://exacheck.net).

## Why ExaCheck

ExaBGP is packaged with its own health checking script ([see here](https://github.com/Exa-Networks/exabgp/blob/main/src/exabgp/application/healthcheck.py)) however it has some limitations which make it not suitable for my requirements. The built in health check works fine for smaller environments where each service may be running its own instance of ExaBGP (so each instance of ExaBGP runs one or only a few processes) however for larger environments where health checks are centralised it becomes unmanageable.

Some features from the built in ExaBGP health checking script are **not** available as they are not relevant to the use case for me:

- Management of IP address binding; the main use case of ExaCheck is for centralised health checks where the service resides on another server/container/VM

### Features

- Live configuration reloads (adding/modifying/removing services)
- Health checks implemented in pure python where possible; no need to write scripts or use chains of commands to validate output
- Detailed logging available
- Configuration validation (if using live configuration reloads, configuration is validated before application)
- Out of the box sane defaults where possible
- JSON schema of configuration (see [schema.json][ExaCheck Configuration Schema] for the current schema)

[ExaCheck Configuration Schema]: https://github.com/exacheck/exacheck/blob/main/schema.json
