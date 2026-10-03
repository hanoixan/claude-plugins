---
role: product | test | manifest
---
# infrastructure: <stack_or_store_name>

<What this provisions and why. If the IaC tool is undecided, use a .iac placeholder and an unknown.>

- **Required:** always | conditional — <condition>
- **Failure modes:** <unavailability, quota, data loss, misconfigured access>
- **Depends on:** none | [<provider or other stack>](<path or URL>)

*UNKNOWN*: [<short-name>] <e.g. cloud provider or IaC tool>. Kind: blocking. Consequence: <...>. Unlocks: <...>.

## resource: <resource_name>

<Purpose of this resource.>

- **Data requirements:** <shape and schema link, volume, growth, retention, consistency, latency, access pattern, security/PII class, backup and restore>
- **Referred by:** [<Consumer.symbol>](<path>)
