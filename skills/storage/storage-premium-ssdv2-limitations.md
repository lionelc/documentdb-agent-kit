# storage-premium-ssdv2-limitations

**Category:** Storage · **Priority:** HIGH

## Why it matters

Premium SSD v2 is the default choice for new Azure DocumentDB clusters, but it has a handful of structural limitations that can block an architecture if discovered late. Surface these *before* picking a storage type, not at the design-review stage.

## Limitations

### 1. Customer-managed keys (CMK) are not supported

Premium SSD v2 clusters use platform-managed encryption only. If your compliance posture mandates CMK / Key Vault–controlled keys, you must use **Premium SSD v1**.

### 2. Storage-capacity changes are rate-limited

Storage capacity on Premium SSD v2 disks can be adjusted at most **four times in any 24-hour window**. For newly created clusters, only **three** capacity changes are allowed during the first 24 hours. Plan capacity moves in batches rather than incrementing repeatedly.

### 3. No online migration from Premium SSD v1 → v2

You can't flip the storage type on an existing cluster. The two supported migration paths are:

- **Point-in-time restore (PITR)** the v1 cluster to a brand-new cluster created on Premium SSD v2.
- Create a **read replica on Premium SSD v2** from the v1 primary, wait for replication to catch up, then promote the replica.

### 4. v1 → v2 replication is migration-only

Replication from a Premium SSD v1 source to a Premium SSD v2 target is supported **only for the migration scenarios above**. Don't architect for ongoing v1 → v2 replication — v1 can't sustain v2 performance and latency will suffer.

## Incorrect

Designing a CMK-required cluster on Premium SSD v2:

```bicep
// Will fail policy / not deploy CMK — Premium SSD v2 doesn't accept customer-managed keys.
storage: { sizeGb: 512, type: 'PremiumSSDv2' }
encryption: {
  customerManagedKeyEncryption: { /* … */ }
}
```

Trying to flip storage type in place:

```bash
# There is no such update path — the property is fixed at creation time.
az rest --method PATCH \
  --url ".../mongoClusters/<name>?api-version=2025-09-01" \
  --body '{"properties":{"storage":{"type":"PremiumSSDv2"}}}'
```

Scripting many small storage bumps:

```bash
# Will hit the 4-changes-per-24h cap quickly.
for size in 256 512 768 1024 1280; do
  az resource update --set properties.storage.sizeGb=$size ...
done
```

## Correct

CMK requirement → Premium SSD v1:

```bicep
storage: {
  sizeGb: 512
  type: 'PremiumSSD'           // v1 is the only CMK-compatible option
}
```

Migrate v1 → v2 via PITR to a new cluster:

```azurecli
az documentdb mongo-cluster restore \
  --resource-group "<rg>" \
  --cluster-name "<new-v2-cluster>" \
  --source-cluster "<existing-v1-cluster>" \
  --restore-time "2026-04-29T10:00:00Z"
# In the restore template, set storage.type = 'PremiumSSDv2'.
```

Or migrate v1 → v2 via replica promotion:

1. Create a replica cluster of the v1 primary with `storage.type = 'PremiumSSDv2'`.
2. Wait for replication lag to reach ~0 (check **Metrics** on the replica).
3. Promote the replica — see `high-availability/ha-cross-region-replica.md` for the runbook.
4. Repoint apps to the promoted cluster's connection string (or use the global RW string and let it follow promotion automatically).
5. Decommission the v1 cluster.

Plan one consolidated capacity change instead of many:

```bash
# Single jump to the target size — stays under the 4-per-24h cap.
az resource update \
  --ids "<cluster-resource-id>" \
  --set properties.storage.sizeGb=1280
```

## References

- [Premium SSD v2 disks — Azure DocumentDB](https://learn.microsoft.com/azure/documentdb/high-performance-storage)
- Related: [`storage-disk-hydration-sequencing`](storage-disk-hydration-sequencing.md), [`high-availability/ha-cross-region-replica`](../high-availability/ha-cross-region-replica.md)
