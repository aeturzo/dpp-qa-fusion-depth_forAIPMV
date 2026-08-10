# Checksums

SHA-256 of every data file in this repository.

| file | rows | sha256 |
|---|---|---|
| `data/examples/table2_multisource.csv` | 3 | `d530798176744972d55d5f19010b8ab97e9b7ff40a53a2f3e7bbb053b26f2356` |
| `data/public_schema/calibration_bins.csv` | 8 | `556a670f4295116cce0b5b9500664627384b67f236a4772c7778e0802d8b31ab` |
| `data/public_schema/ranked_risk_coverage.csv` | 5,868 | `b42aeaef29a6d44e1f195e36437b0e9da6482512f86b33ed915b761f257fa3ab` |
| `data/public_schema/system_eval_summary.csv` | 6 | `bee61cd5d51183aa8623bc441e6f0cc8ed8f52df2ef53e3de9467097c9ffd50b` |
| `data/verified/eval_depth_aware.csv` | 6,270 | `b193141e0105dfcaeb0302f47326e6dba5c06521153af7437e480fee6351694b` |
| `data/verified/eval_linc.csv` | 6,270 | `8bade190b4cab2fa3a4ade2cc6a35782a3a3b90dfd2af7c016350ced58490c0e` |
| `data/verified/eval_logiclm.csv` | 6,270 | `89f4203f1229b72636023b0299d63998f1e4f7023820380a4bda0a69ddf86e63` |
| `data/verified/eval_longctx.csv` | 6,270 | `85ad5d7a3981a8e3090d698543c7caefed8905774e00891b678dc80afd798be5` |
| `data/verified/exclusions.csv` | 645 | `b40404b51764b8718626a54b1e27ef083d30bbbd2b2498e4d3ae37799a0dd90d` |

## Columns withheld from the per-question files

These describe how the system under study works and are deferred with the system description. No reported number depends on them.

| column | reason |
|---|---|
| `mode` | names the internal configuration |
| `steps` | full execution trace including symbolic derivations |
| `n_steps` | execution shape |
| `latency_ms` | timing |
| `confidence` | internal scoring, unused by any reported number |
| `confidence_raw` | internal scoring |
| `confidence_cal` | internal scoring |
| `cost_retrieval_calls` | internal call counts |
| `cost_rule_checks` | internal call counts |
| `cost_tokens_in` | token accounting |
| `cost_tokens_out` | token accounting |
| `cost_usd_running` | spend |
| `success` | duplicate of `correct` |
| `session` | run-harness session label, unused by any reported number |
