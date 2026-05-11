# ha-cross-region-replica

**Category:** High Availability & Replication · **Priority:** MEDIUM

## Why it matters

Azure DocumentDB supports **active-passive cross-region replication**: one cluster is the read-write primary, a replica cluster in another region stays read-only and in sync. If a region fails, the replica can be promoted to take writes with minimal interruption. Combined with in-region HA, this delivers the **99.995% SLA** and enables:
- Disaster recovery across regions.
- Read-scale offload to the replica for heavy analytical reads or for region-local reads close to distant users.

Two things to internalize before designing for cross-region:

- **Replication is asynchronous.** Replica reads are eventually consistent — writes acknowledged on the primary may not yet be visible on the replica. Applications that need read-your-own-writes must route those reads to the primary.
- **Failover is *not* automatic across regions.** Per the Azure shared-responsibility model, you (the customer) own the DR plan. Region failover requires a **customer-triggered promotion** of the replica. In-region HA failover is automatic; cross-region promotion is not.

## Incorrect

Relying solely on in-region HA for a mission-critical global application:

```text
Single-region cluster, HA: on
- Survives node and zone failures (good)
- Does NOT survive regional outage
- No automatic cross-region failover
- No read-scale offload for distant users
```

## Correct

Pair HA + cross-region replica for production-critical workloads:

1. Enable HA on the primary cluster (see `ha-enable-for-production`).
2. Create a replica cluster (`createMode: 'GeoReplica'`) in a paired or geographically near region. The replica reuses the primary's admin credentials, databases, collections, and documents — only the cluster name and region differ.
3. Enable HA on the replica too — required for the combined 99.995 % SLA and for AZ placement after promotion.
4. Route latency-sensitive reads in that region to the replica's connection string (read-only).
5. Document and **periodically test** a promotion runbook for DR.

```text
Primary:   East US 2  (read-write, HA on)
Replica:   West US 3  (read-only,  HA on)
Combined SLA: 99.995%
```

Design for eventual consistency on the replica; writes must still target the primary until you explicitly promote the replica.

### Region selection

Pick the replica region with three trade-offs in mind:

| Factor | Guidance |
|---|---|
| **Network latency from primary to replica** | Closer regions = lower replication lag. Prefer geographically near regions when reads from the replica must be near-fresh. |
| **Write-path latency on the primary** | Asynchronous replication does not block writes, but cross-region traffic still costs egress and adds operational risk. Don't over-replicate "just in case." |
| **DR isolation** | The replica must be in a **different region** from the primary to survive a regional outage. For paired-region semantics, prefer an Azure region pair. |
| **Read-locality** | If the goal is read scale-out for users in a specific geography, pick the region nearest those users — not the one nearest the primary. |

### Read scale-out routing

Use two connection strings in the application:

- **Writes & strongly-consistent reads** → primary cluster connection string (use the **Global read-write** hostname `<cluster>.global.mongocluster.cosmos.azure.com` so it auto-follows promotion).
- **Region-local / analytical reads** → replica's read-only connection string.

This is the only way to offload reads; there is no implicit read-routing in the driver. Document which queries are safe to route to the replica and which require the primary.

### Bicep — replica cluster

The replica is a separate `Microsoft.DocumentDB/mongoClusters` resource with `createMode: 'GeoReplica'` and a `replicaParameters` block that points at the primary's resource ID and location. Most data-plane fields (admin, server version, sharding, storage, compute) are inherited from the source and **must not** be set on the replica.

```bicep
@description('Resource ID of the primary (source) cluster.')
param primaryClusterId string

@description('Azure region of the primary cluster.')
param primaryLocation string

@description('Azure region for the replica cluster (different from the primary for cross-region DR).')
param replicaLocation string

@description('Globally unique replica cluster name.')
param replicaClusterName string

resource replica 'Microsoft.DocumentDB/mongoClusters@2025-09-01' = {
  name:     replicaClusterName
  location: replicaLocation
  properties: {
    createMode: 'GeoReplica'
    replicaParameters: {
      sourceResourceId: primaryClusterId
      sourceLocation:   primaryLocation
    }
    // Recommended: enable HA on the replica too for the 99.995% combined SLA.
    highAvailability: {
      targetMode: 'ZoneRedundantPreferred'
    }
  }
}

output replicaId string = replica.id
```

Deploy after the primary exists (the API requires the source cluster to be in a ready state):

```bash
az deployment group create \
  --resource-group rg-docdb-replica \
  --template-file replica.bicep \
  --parameters \
      primaryClusterId="/subscriptions/<sub>/resourceGroups/rg-docdb-prod/providers/Microsoft.DocumentDB/mongoClusters/docdb-prod-001" \
      primaryLocation=eastus2 \
      replicaLocation=westus3 \
      replicaClusterName=docdb-prod-001-replica
```

The replica may be deployed into a **different resource group** (and even a different region's RG) than the primary; only `sourceResourceId` and `sourceLocation` matter for linkage.

### Terraform — replica cluster

Requires AzureRM provider **4.15+** (earlier 4.x versions reject `create_mode = "GeoReplica"`). With `GeoReplica`, the data-plane attributes (`administrator_*`, `compute_tier`, `shard_count`, `storage_size_in_gb`, `version`) are inherited from the source and should be omitted.

```hcl
resource "azurerm_mongo_cluster" "replica" {
  name                = "docdb-prod-001-replica"
  resource_group_name = azurerm_resource_group.replica_rg.name
  location            = "westus3"

  create_mode      = "GeoReplica"
  source_server_id = azurerm_mongo_cluster.primary.id
  source_location  = azurerm_mongo_cluster.primary.location

  high_availability_mode = "ZoneRedundantPreferred"   # combined 99.995% SLA
}
```

If the replica is in a separate Terraform state, hard-code `source_server_id` and `source_location` (or read them via an `azurerm_mongo_cluster` data source) instead of referencing the resource directly.

### Promotion (DR failover)

Promotion is a control-plane action (REST / portal); there is no IaC primitive for it. After promotion, the former replica becomes a standalone read-write cluster — update the IaC to drop `createMode` / `create_mode` and `replicaParameters` so subsequent runs don't try to re-link it. See [Replica cluster promotion](https://learn.microsoft.com/azure/documentdb/cross-region-replication#replica-cluster-promotion).

## References

- [HA & cross-region replication best practices](https://learn.microsoft.com/azure/documentdb/high-availability-replication-best-practices)
- [Reliability in Azure DocumentDB](https://learn.microsoft.com/azure/reliability/reliability-documentdb) — shared-responsibility DR model, manual cross-region promotion
- [Cross-region replication](https://learn.microsoft.com/azure/documentdb/cross-region-replication)
- [Manage cluster replication](https://learn.microsoft.com/azure/documentdb/how-to-cluster-replica)
- [`MongoClusterReplicaParameters` (ARM/Bicep)](https://learn.microsoft.com/azure/templates/microsoft.documentdb/mongoclusters#mongoclusterreplicaparameters)
- [`azurerm_mongo_cluster` — `create_mode`, `source_server_id`, `source_location`](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/mongo_cluster)
