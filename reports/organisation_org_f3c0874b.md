# CR-006 STOP 2: organisation `org_f3c0874b`

Run `pdcanon2_30e2b4f9`, mode provisional, radius basis (config default, owner to confirm) **adjusted**, config e9ad6312dab7, code 4fe7653. Label source: Structural metric (no human labels). No API calls.

## Chapter 2

419 concepts, 72 typed edges (semantic + taxonomy); eligible for rings 63; **unlinked 356** (85%); background 0. Modularity coarse 0.647, fine 0.658.

### Top 15: raw vs adjusted importance

| # | raw: concept | raw | adjusted: concept | adj |
|---|---|---|---|---|
| 1 | link | 0.932 | CRC | 1.000 |
| 2 | frame | 0.881 | link | 0.984 |
| 3 | CRC | 0.875 | softwarization | 0.968 |
| 4 | Internet | 0.814 | frame | 0.952 |
| 5 | network | 0.810 | Internet | 0.935 |
| 6 | bit | 0.810 | last-mile link | 0.919 |
| 7 | last-mile link | 0.805 | network | 0.903 |
| 8 | wireless link | 0.763 | bit | 0.887 |
| 9 | copper wire | 0.744 | wireless link | 0.871 |
| 10 | wire | 0.725 | copper wire | 0.855 |
| 11 | air | 0.698 | base station | 0.839 |
| 12 | checksum | 0.666 | checksum | 0.823 |
| 13 | optical fiber | 0.663 | wire | 0.806 |
| 14 | SONET | 0.641 | air | 0.790 |
| 15 | encoding | 0.634 | cloud | 0.766 |

Overlap of the two top-15 lists: 12/15.

### Background vocabulary (generic guard)

(none flagged)

### Is there a core? (Borgatti-Everett fit vs nulls)

| | value |
|---|---|
| nodes / edges in the fit | 63 / 72 |
| rho observed | 0.297 |
| primary null (same-density random, n=200) | mean 0.118 ± 0.0385, z 4.6, delta-rho 0.179 |
| secondary null (degree-preserving; reported, not gated) | mean 0.257 ± 0.0340, z 1.2, delta-rho 0.040 |
| **label (gated on the primary null)** | **core-periphery structure present** |

### Stability

n/a (first snapshot).

### Review flags (a flag is never a deletion or demotion)

- **persistent_unlinked: 0** concepts with no typed edge in >= 2 consecutive snapshots (a relation-recall signal).
- **persistent_periphery: 0** concepts that are linked but in the outer ring in >= 2 consecutive snapshots (the real review list).

## Chapter 3

736 concepts, 121 typed edges (semantic + taxonomy); eligible for rings 104; **unlinked 632** (86%); background 0. Modularity coarse 0.673, fine 0.697.

### Top 15: raw vs adjusted importance

| # | raw: concept | raw | adjusted: concept | adj |
|---|---|---|---|---|
| 1 | link | 0.962 | switch | 1.000 |
| 2 | switch | 0.906 | link | 0.990 |
| 3 | network | 0.903 | CRC | 0.981 |
| 4 | frame | 0.886 | network | 0.971 |
| 5 | CRC | 0.883 | frame | 0.961 |
| 6 | Ethernet | 0.867 | checksum | 0.951 |
| 7 | router | 0.858 | Ethernet | 0.942 |
| 8 | checksum | 0.850 | router | 0.932 |
| 9 | bit | 0.824 | softwarization | 0.922 |
| 10 | Internet | 0.818 | Internet | 0.913 |
| 11 | last-mile link | 0.799 | bit | 0.903 |
| 12 | wireless link | 0.780 | last-mile link | 0.893 |
| 13 | copper wire | 0.778 | copper wire | 0.883 |
| 14 | softwarization | 0.742 | wireless link | 0.874 |
| 15 | local area network | 0.735 | L2 network | 0.864 |

Overlap of the two top-15 lists: 14/15.

### Background vocabulary (generic guard)

(none flagged)

### Is there a core? (Borgatti-Everett fit vs nulls)

| | value |
|---|---|
| nodes / edges in the fit | 104 / 121 |
| rho observed | 0.251 |
| primary null (same-density random, n=200) | mean 0.091 ± 0.0214, z 7.5, delta-rho 0.160 |
| secondary null (degree-preserving; reported, not gated) | mean 0.246 ± 0.0202, z 0.2, delta-rho 0.005 |
| **label (gated on the primary null)** | **core-periphery structure present** |

### Stability vs previous chapter

Core (centre + inner) Jaccard 0.62; Kendall tau over 63 shared nodes 0.73; mean displacement 0.061 (unit disc).

### 10 biggest movers (change in adjusted importance percentile)

| concept | ring | change | new edges behind it |
|---|---|---|---|
| node | outer -> middle | +0.626 | routing -[requires]-> node (3.4) |
| datacenter | middle -> outer | -0.456 | cloud -[uses]-> Virtual LAN (3-perspective-virtual-networks-all-the-way-down); local area network -[part_of]-> cloud (3-perspective-virtual-networks-all-the-way-down) |
| spectrum | middle -> outer | -0.436 | (neighbourhood shift; no new edge on the concept itself) |
| Central Office | middle -> outer | -0.389 | network -[increases]-> path (3-problem-not-all-networks-are-directly-connected); tenant -[uses]-> network (3-perspective-virtual-networks-all-the-way-down); Virtual LAN -[has_purpose]-> network (3-perspective-virtual-networks-all-the-way-down); switch -[has_purpose]-> network (3.1) |
| OLT | outer -> outer | -0.313 | (neighbourhood shift; no new edge on the concept itself) |
| ACK | middle -> outer | -0.305 | Sequence number -[part_of]-> header (2.5) |
| radio spectrum | outer -> outer | -0.280 | (neighbourhood shift; no new edge on the concept itself) |
| Ethernet | middle -> inner | +0.264 | Ethernet -[has_property]-> address (2.6); protocol -[has_purpose]-> Ethernet (2.6) |
| collision | outer -> outer | -0.264 | (neighbourhood shift; no new edge on the concept itself) |
| network edge | middle -> outer | -0.262 | network edge -[is_a]-> edge (2-perspective-race-to-the-edge) |

### Review flags (a flag is never a deletion or demotion)

- **persistent_unlinked: 344** concepts with no typed edge in >= 2 consecutive snapshots (a relation-recall signal).
- **persistent_periphery: 30** concepts that are linked but in the outer ring in >= 2 consecutive snapshots (the real review list).

