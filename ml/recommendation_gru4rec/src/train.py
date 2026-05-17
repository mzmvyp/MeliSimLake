"""GRU4Rec — treino completo com MLflow logging."""

from __future__ import annotations

import mlflow
import numpy as np
import torch
import torch.nn as nn
from loguru import logger
from torch.utils.data import DataLoader, random_split

from ml.recommendation_gru4rec.src.data import SessionDataset, build_item_index, collate_fn
from ml.recommendation_gru4rec.src.model import GRU4Rec
from ml.shared.metrics import mrr_at_k, recall_at_k
from ml.shared.mlflow_helpers import register_model, setup_mlflow, start_run

EXPERIMENT_NAME = "melisimlake/recommendation_gru4rec"
MODEL_NAME = "recommendation_gru4rec"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _load_sequences() -> list[list[int]]:
    """Carrega sequências de produtos por sessão."""
    try:
        from ml.shared.feature_loader import load_session_sequences

        df = load_session_sequences()
        if not df.empty and "product_sequence" in df.columns:
            return [seq for seq in df["product_sequence"].tolist() if len(seq) >= 2]
    except Exception as exc:
        logger.warning("feature_loader indisponível", extra={"error": str(exc)})

    rng = np.random.default_rng(42)
    n_sessions, vocab_size = 10_000, 1_000
    return [
        rng.integers(1, vocab_size, size=rng.integers(2, 30)).tolist()
        for _ in range(n_sessions)
    ]


def _train_epoch(
    model: GRU4Rec,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
) -> float:
    model.train()
    total_loss = 0.0
    for sessions, targets, lengths in loader:
        sessions, targets = sessions.to(DEVICE), targets.to(DEVICE)
        lengths = lengths.to(DEVICE)
        optimizer.zero_grad()
        logits = model(sessions, lengths)
        loss = criterion(logits, targets)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        optimizer.step()
        total_loss += loss.item()
    return total_loss / len(loader)


@torch.no_grad()
def _evaluate(model: GRU4Rec, loader: DataLoader, k: int = 20) -> dict[str, float]:
    model.eval()
    all_recs, all_rel = [], []
    for sessions, targets, lengths in loader:
        sessions = sessions.to(DEVICE)
        logits = model(sessions, lengths.to(DEVICE))
        top_k = logits.topk(k, dim=1).indices.cpu().tolist()
        all_recs.extend(top_k)
        all_rel.extend([[t.item()] for t in targets])
    return {
        f"recall@{k}": recall_at_k(all_recs, all_rel, k),
        f"mrr@{k}": mrr_at_k(all_recs, all_rel, k),
    }


def run(
    run_date: str = "2026-01-01",
    epochs: int = 20,
    batch_size: int = 512,
) -> str:
    """Treina GRU4Rec e registra no MLflow.

    Args:
        run_date: Data de referência.
        epochs: Número de épocas.
        batch_size: Tamanho do batch.

    Returns:
        MLflow run_id.
    """
    setup_mlflow(EXPERIMENT_NAME)
    seqs = _load_sequences()
    item_idx = build_item_index(seqs)
    indexed = [[item_idx.get(i, 0) for i in seq] for seq in seqs]

    dataset = SessionDataset(indexed)
    val_size = max(1, int(len(dataset) * 0.1))
    train_size = len(dataset) - val_size
    train_ds, val_ds = random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, collate_fn=collate_fn)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, collate_fn=collate_fn)

    n_items = max(item_idx.values()) + 1
    model = GRU4Rec(n_items=n_items).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    criterion = nn.CrossEntropyLoss(ignore_index=0)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3, factor=0.5)

    logger.info("GRU4Rec treino iniciado", extra={"device": str(DEVICE), "n_items": n_items, "epochs": epochs})

    with start_run(f"gru4rec_{run_date}", tags={"model": "GRU4Rec"}) as run:
        mlflow.log_params(
            {
                "n_items": n_items,
                "embedding_dim": 128,
                "hidden_dim": 256,
                "epochs": epochs,
                "batch_size": batch_size,
                "n_sequences": len(seqs),
            }
        )

        for epoch in range(1, epochs + 1):
            loss = _train_epoch(model, train_loader, optimizer, criterion)
            metrics = _evaluate(model, val_loader)
            scheduler.step(loss)

            mlflow.log_metric("train_loss", loss, step=epoch)
            for k, v in metrics.items():
                mlflow.log_metric(k, v, step=epoch)

            if epoch % 5 == 0:
                logger.info("Epoch", extra={"epoch": epoch, "loss": loss, **metrics})

        mlflow.pytorch.log_model(model, "model")
        run_id = run.info.run_id

    register_model(f"runs:/{run_id}/model", MODEL_NAME, stage="Staging")
    logger.info("GRU4Rec treinado", extra={"run_id": run_id})
    return run_id


if __name__ == "__main__":
    run()
