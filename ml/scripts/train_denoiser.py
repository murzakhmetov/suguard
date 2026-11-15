"""Train the motion-artefact denoiser and export it to ONNX.

    python scripts/train_denoiser.py --data data/denoiser --steps 12000 --out models

Runs on CPU (about an hour for the default settings on 4 cores) or GPU
(Colab: a few minutes). Writes models/denoiser.onnx, models/denoiser.pt and
models/metrics/denoiser_train.json.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suguard_ml.config import FS, WINDOW  # noqa: E402
from suguard_ml.eval.vitals_eval import both_finite, summarize_errors, vitals_from_bv  # noqa: E402
from suguard_ml.models.denoiser_net import build_model, denoiser_loss  # noqa: E402


def load_split(path: Path):
    d = np.load(path)
    return d["X"], d["Y"], d["M"], d["meta"]


def batches(X, Y, M, bs, rng):
    n = X.shape[0]
    while True:
        idx = rng.permutation(n)
        for i in range(0, n - bs + 1, bs):
            j = np.sort(idx[i:i + bs])
            yield (torch.from_numpy(X[j].astype(np.float32)),
                   torch.from_numpy(Y[j].astype(np.float32)),
                   torch.from_numpy(M[j].astype(np.float32)))


@torch.no_grad()
def evaluate(model, X, Y, M, meta, device, n_vitals=600):
    model.eval()
    losses = []
    outs = []
    for i in range(0, X.shape[0], 256):
        x = torch.from_numpy(X[i:i + 256].astype(np.float32)).to(device)
        y = torch.from_numpy(Y[i:i + 256].astype(np.float32)).to(device)
        m = torch.from_numpy(M[i:i + 256].astype(np.float32)).to(device)
        out = model(x)
        _, parts = denoiser_loss(out, y, m)
        losses.append(parts)
        outs.append(out.cpu().numpy())
    out = np.concatenate(outs)
    res = {k: float(np.mean([p[k] for p in losses])) for k in losses[0]}
    # Mask head quality.
    p = 1 / (1 + np.exp(-out[:, 2]))
    from sklearn.metrics import roc_auc_score
    try:
        res["mask_auc"] = float(roc_auc_score(M.reshape(-1)[::7], p.reshape(-1)[::7]))
    except ValueError:
        res["mask_auc"] = None
    # Downstream vitals on a subset (scale cancels for HR/SpO2).
    k = min(n_vitals, X.shape[0])
    rows_dn = [vitals_from_bv(out[i, 0], out[i, 1], FS, p[i]) for i in range(k)]
    rows_raw = [vitals_from_bv(X[i, 0].astype(np.float64), X[i, 1].astype(np.float64), FS) for i in range(k)]
    hr, spo2 = meta[:k, 0], meta[:k, 1]
    flagged_ok = np.array([r["artifact_frac"] < 0.5 for r in rows_dn])
    common = both_finite(rows_raw, rows_dn)
    res["vitals_raw"] = summarize_errors(rows_raw, hr, spo2)
    res["vitals_denoised"] = summarize_errors(rows_dn, hr, spo2)
    res["vitals_raw_common"] = summarize_errors(rows_raw, hr, spo2, common=common)
    res["vitals_denoised_common"] = summarize_errors(rows_dn, hr, spo2, common=common)
    res["vitals_denoised_confident"] = summarize_errors(rows_dn, hr, spo2, keep=flagged_ok)
    model.train()
    return res


def export_onnx(model, path: Path):
    model = model.cpu().eval()
    dummy = torch.randn(1, 2, WINDOW)
    torch.onnx.export(model, dummy, str(path), input_names=["x"], output_names=["y"],
                      dynamic_axes={"x": {0: "batch"}, "y": {0: "batch"}}, opset_version=17,
                      dynamo=False)
    import onnxruntime as ort
    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    xt = torch.randn(4, 2, WINDOW)
    ref = model(xt).detach().numpy()
    got = sess.run(None, {"x": xt.numpy()})[0]
    err = float(np.max(np.abs(ref - got)))
    print(f"ONNX export ok, max |torch - onnx| = {err:.2e}")
    return err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/denoiser")
    ap.add_argument("--out", default="models")
    ap.add_argument("--steps", type=int, default=12000)
    ap.add_argument("--bs", type=int, default=128)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--eval-every", type=int, default=1000)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--arch", default="unet", choices=["unet", "edge"],
                    help="unet: server model; edge: small model for the ESP32-C3 firmware")
    ap.add_argument("--chans", default=None, help="comma-separated channel widths, e.g. 8,16,24,32")
    ap.add_argument("--name", default=None, help="output file stem (default: denoiser / denoiser_edge)")
    a = ap.parse_args()
    chans = [int(c) for c in a.chans.split(",")] if a.chans else None
    name = a.name or ("denoiser" if a.arch == "unet" else "denoiser_edge")

    torch.manual_seed(a.seed)
    torch.set_num_threads(a.threads)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    data = Path(a.data)
    out = Path(a.out)
    (out / "metrics").mkdir(parents=True, exist_ok=True)

    Xtr, Ytr, Mtr, _ = load_split(data / "train.npz")
    Xva, Yva, Mva, meta_va = load_split(data / "val.npz")
    print(f"train {Xtr.shape}, val {Xva.shape}, device {device}")

    model = build_model(a.arch, chans).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"params: {n_params:,}")
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / 300) * 0.5 * (1 + math.cos(math.pi * min(s / a.steps, 1.0))))

    rng = np.random.default_rng(a.seed)
    it = batches(Xtr, Ytr, Mtr, a.bs, rng)
    best, history, t0 = math.inf, [], time.time()
    running = []
    for step in range(1, a.steps + 1):
        x, y, m = (t.to(device) for t in next(it))
        loss, parts = denoiser_loss(model(x), y, m)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        running.append(loss.item())
        if step % 100 == 0:
            print(f"step {step} loss {np.mean(running):.4f} lr {sched.get_last_lr()[0]:.2e} "
                  f"{(time.time() - t0) / step * 1000:.0f} ms/step", flush=True)
            running = []
        if step % a.eval_every == 0 or step == a.steps:
            res = evaluate(model, Xva, Yva, Mva, meta_va, device)
            score = res["wave"] + res["deriv"] + 0.5 * res["ratio"]
            res["step"] = step
            history.append(res)
            print(json.dumps({k: v for k, v in res.items() if not k.startswith("vitals")}),
                  "\n  raw  ", res["vitals_raw"]["hr"], res["vitals_raw"]["spo2"],
                  "\n  dn   ", res["vitals_denoised"]["hr"], res["vitals_denoised"]["spo2"],
                  "\n  dn-ok", res["vitals_denoised_confident"]["selected_fraction"],
                  res["vitals_denoised_confident"]["hr"], res["vitals_denoised_confident"]["spo2"], flush=True)
            if score < best:
                best = score
                torch.save({"state_dict": model.state_dict(), "step": step, "val": res,
                            "arch": a.arch, "chans": chans}, out / f"{name}.pt")

    ckpt = torch.load(out / f"{name}.pt", map_location="cpu")
    model.load_state_dict(ckpt["state_dict"])
    err = export_onnx(model, out / f"{name}.onnx")
    summary = {"arch": a.arch, "chans": chans, "params": n_params, "steps": a.steps, "best_step": ckpt["step"],
               "best_val": ckpt["val"],
               "history": history, "onnx_max_abs_err": err, "train_windows": int(Xtr.shape[0]),
               "minutes": (time.time() - t0) / 60}
    (out / "metrics" / f"{name}_train.json").write_text(json.dumps(summary, indent=2))
    print("done", json.dumps(ckpt["val"]["vitals_denoised"], indent=1))


if __name__ == "__main__":
    main()
