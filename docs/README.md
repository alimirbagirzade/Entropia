# Entropia V18 — Documentation

| Document | Purpose |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture: process topology, layering, data split, job/worker model, backtest & agent planes, SSE, API conventions, observability, deployment. |
| [DOMAIN_MODEL.md](DOMAIN_MODEL.md) | Canonical roots/revisions/snapshots, lifecycle enum registry, role model, ownership & shared-editing rules, soft-delete/trash, audit, and the CR-01..CR-09 invariants. |
| [STAGE_BUILD_PLAN.md](STAGE_BUILD_PLAN.md) | The Stage 0..8 build roadmap mapping every screen/domain to its stage with acceptance criteria. |
| [spec/](spec/) | **Source specification (canonical authority).** The Master Technical Reference, 22 page documents, the staged coding prompt set, and the V18 visual prototype. |

## Authority order (binding)

1. `spec/Entropia_V18_Master_Technical_Reference_v1_0.md` — canonical, final authority.
2. `spec/NN_*_Page_Documentation_v1_1.md` — the implementation contract for each screen.
3. The synthesized docs above — engineering interpretation; if they conflict with the spec, the spec wins.
4. `spec/index_guncellenmis_duzeltilmis_v18.html` — visual/prototype reference only (never authoritative for persistence, authorization, lifecycle, or API behavior).
