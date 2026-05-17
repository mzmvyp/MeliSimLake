"""SASRec — treino."""

from __future__ import annotations

import mlflow
import numpy as np
import torch
import torch.nn as nn
from loguru import logger
from torch.utils.data import DataLoader, random_split

from ml.recommendation_gru4rec.src.data import SessionDataset, build_item_index, collate_fn
from ml.recommendation_sasrec.src.model import SASRec
from ml.shared.metrics import mrr_at_k, recall_at_k
from ml.shared.mlflow_helpers import register_model, setup_mlflow, start_run

EXPERIMENT_NAME = "melisimlake/recommendation_sasrec"
MODEL_NAME = "recommendation_sasrec"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def run(
    run_date: str = "2026-01-01",
    epochs: int = 20,
    batch_size: int = 256,
) -> str:
    """Treina SASRec e registra no MLflow.

    Args:
        run_date: Data de referência.
        epochs: Número de épocas.
        batch_size: Tamanho do batch.

    Returns:
        MLflow run_id.
    """
    setup_mlflow(EXPERIMENT_NAME)
    rng = np.random.default_rng(42)
    seqs = [rng.integers(1, 1000, size=rng.integers(2, 30)).tolist() for _ in range(10_000)]
    item_idx = build_item_index(seqs)
    indexed = [[item_idx.get(i, 0) for i in seq] for seq in seqs]

    dataset = SessionDataset(indexed, max_len=50)
    val_size = max(1, int(len(dataset) * 0.1))
    train_ds, val_ds = random_split(dataset, [len(dataset) - val_size, val_size])
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, collate_fn=collate_fn)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, collate_fn=collate_fn)

    n_items = max(item_idx.values()) + 1
    model = SASRec(n_items=n_items).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    criterion = nn.CrossEntropyLoss(ignore_index=0)

    logger.info("SASRec treino iniciado", extra={"device": str(DEVICE), "n_items": n_items})

    with start_run(f"sasrec_{run_date}", tags={"model": "SASRec"}) as run:
        mlflow.log_params({"n_items": n_items, "embedding_dim": 128, "n_heads": 4, "n_layers": 2, "epochs": epochs})

        for epoch in range(1, epochs + 1):
            model.train()
            total_loss = 0.0
            for sessions, targets, lengths in train_loader:
                sessions, targets = sessions.to(DEVICE), targets.to(DEVICE)
                optimizer.zero_grad()
                logits = model(sessions, lengths.to(DEVICE))
                loss = criterion(logits, targets)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                optimizer.step()
                total_loss += loss.item()

            avg_loss = total_loss / len(train_loader)
            mlflow.log_metric("train_loss", avg_loss, step=epoch)

            if epoch % 5 == 0:
                model.eval()
                all_recs, all_rel = [], []
                with torch.no_grad():
                    for sessions, targets, lengths in val_loader:
                        logits = model(sessions.to(DEVICE), lengths.to(DEVICE))
                        top_k = logits.topk(20, dim=1).indices.cpu().tolist()
                        all_recs.extend(top_k)
                        all_rel.extend([[t.item()] for t in targets])
                r20 = recall_at_k(all_recs, all_rel, 20)
                mrr = mrr_at_k(all_recs, all_rel, 20)
                mlflow.log_metrics({"val_recall@20": r20, "val_mrr@20": mrr}, step=epoch)
                logger.info("Epoch SASRec", extra={"epoch": epoch, "loss": avg_loss, "recall@20": r20})

        mlflow.pytorch.log_model(model, "model")
        run_id = run.info.run_id

    register_model(f"runs:/{run_id}/model", MODEL_NAME, stage="Staging")
    return run_id


if __name__ == "__main__":
    run()
