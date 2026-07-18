# ML Specialist Mesh And Hybrid Playbook

Status: candidate, provider-neutral, no execution authority.

This playbook extends `skill:ml-workflow-agent-family`. It does not create a
second ML family. Every route begins with `asset-dir ml fit`, carries the exact
receipt through `asset-dir ml specialist-route`, and keeps one bounded writer
and an independent checker.

## Demand-Activated Mesh

| Need | Specialist | Default comparison | Stop or escalate when |
|---|---|---|---|
| Structured classification, regression, ranking | `ml-tabular-boosting-specialist` | regularized linear model and a simple tree | leakage, weak lift, unstable calibration, or unsupported categorical semantics |
| Sparse memorization plus nonlinear generalization | `ml-wide-deep-representation-specialist` | linear/GBDT and single-tower model | sample size, latency, or ablation evidence does not justify two paths |
| Text/image/audio representations joined to structured data | `ml-wide-deep-representation-specialist` | frozen encoder plus simple head; tabular-only GBDT | encoder provenance, train/test overlap, or component value is unknown |
| Nodes, edges, graphs, or retrieval ranking | `ml-graph-ranking-specialist` | flat features and governed retrieval baseline | edge authority, transductive leakage, or candidate recall is unknown |
| Forecasts and decision intervals | `ml-temporal-uncertainty-specialist` | seasonal naive/statistical baseline | rolling coverage, availability-time, or regime-shift checks fail |
| Treatment effects or intervention choice | `ml-causal-decision-specialist` | descriptive/predictive baseline plus explicit causal design | identification, overlap, interference, or sensitivity evidence is missing |
| Label-efficient review or sequential choice | `ml-active-online-learning-specialist` | random/diversity sampling or fixed policy | uncertainty is uncalibrated or exploration is unsafe |
| Data-local or privacy-bounded training | `ml-privacy-federated-specialist` | local-only and approved aggregate baselines | threat model, accounting, poisoning, or heterogeneity evidence is absent |
| Model packaging, evaluation, drift, rollback | `ml-operations-evaluation-specialist` | current approved artifact or no-model fallback | signature, owner, monitor, rollback, or retraining approval is undefined |

The foreman activates only the specialists needed by the locked experiment.
Specialists advise or implement within a bounded packet; none self-approve.

## High-Value Compositions

1. **Embeddings + XGBoost:** freeze a reviewed encoder, join embeddings to
   structured features, and compare tabular-only, embedding-only, and combined
   models. This is often the strongest low-complexity multimodal challenger.
2. **Retrieval/graph + ranker:** let Knowledge Engineering own source and graph
   authority, measure candidate recall, then use XGBoost or wide-and-deep for
   ranking. Never let ranking metrics hide retrieval misses.
3. **Forecast + conformal interval:** produce a temporal point or quantile
   forecast, calibrate residual intervals on later data, and monitor rolling
   coverage by horizon and slice.
4. **Double ML + flexible nuisance models:** use boosting or neural estimators
   for nuisance functions while sample splitting and identification assumptions
   control the causal claim.
5. **Calibrated uncertainty + diversity:** rank active-learning candidates by
   reviewed uncertainty and diversity, retain abstention, and audit the new
   sample for feedback-loop bias.
6. **Federated representation + local heads:** consider only after a formal
   privacy and attack model; compare against local-only training and inspect
   client heterogeneity and poisoning behavior.

## End-To-End Evidence Flow

`fit receipt -> data/leakage contract -> baseline -> specialist or hybrid
contract -> bounded build -> component ablations -> calibration/robustness/
cost -> independent replay -> immutable model card and PredictContract ->
human deployment gate -> monitoring, retraining approval, rollback`

## Primary Sources Used For This Revision

- XGBoost documentation: https://xgboost.readthedocs.io/en/stable/
- Wide & Deep Learning: https://arxiv.org/abs/1606.07792
- TabTransformer: https://arxiv.org/abs/2012.06678
- Transformer architecture: https://arxiv.org/abs/1706.03762
- PyTorch Geometric introduction: https://pytorch-geometric.readthedocs.io/en/latest/tutorial/create_gnn.html
- Temporal Fusion Transformer: https://arxiv.org/abs/1912.09363
- Double/debiased machine learning: https://arxiv.org/abs/1608.00060
- Conformalized quantile regression: https://arxiv.org/abs/1905.03222
- SimCLR self-supervised learning: https://arxiv.org/abs/2002.05709
- Federated averaging: https://arxiv.org/abs/1602.05629
- MLflow model signatures and evaluation: https://mlflow.org/docs/latest/ml/model/signatures/ and https://mlflow.org/docs/latest/ml/evaluation/
- Hugging Face model cards and evaluator: https://huggingface.co/docs/hub/en/model-cards and https://huggingface.co/docs/evaluate/en/base_evaluator
- NIST AI RMF Core: https://airc.nist.gov/airmf-resources/airmf/5-sec-core/

These pointers are candidate research evidence. Library adoption, data access,
training, deployment, automation, and cross-repository changes remain separately
authorized decisions.