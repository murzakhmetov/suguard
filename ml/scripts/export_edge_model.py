"""Quantise a trained edge denoiser and export it for the firmware.

    python scripts/export_edge_model.py --ckpt data/edge_s/denoiser_edge.pt --data data/denoiser

(these are the defaults, taken relative to the ml/ folder wherever the script is started)

Writes
    models/denoiser_edge_int.npz               integer model (Python reference format)
    models/denoiser_edge.onnx                  the float model, for comparison
    ../firmware/suguard/src/core/sg_model.h    weights compiled into the firmware
    models/metrics/denoiser_edge_export.json   size and float-vs-integer agreement
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suguard_ml.models import edge_int as E  # noqa: E402
from suguard_ml.models.denoiser_net import build_model  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ML = ROOT / "ml"            # the defaults do not depend on the directory the script is started from


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=str(ML / "data" / "edge_s" / "denoiser_edge.pt"),
                    help="checkpoint written by train_denoiser.py --arch edge")
    ap.add_argument("--data", default=str(ML / "data" / "denoiser"), help="dataset the model was trained on")
    ap.add_argument("--out", default=str(ML / "models"))
    ap.add_argument("--header", default=str(ROOT / "firmware" / "suguard" / "src" / "core" / "sg_model.h"))
    ap.add_argument("--calib", type=int, default=2000, help="training windows used for calibration")
    a = ap.parse_args()

    ckpt = torch.load(a.ckpt, map_location="cpu")
    model = build_model(ckpt.get("arch", "edge"), ckpt.get("chans"))
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    train = np.load(Path(a.data) / "train.npz")
    rng = np.random.default_rng(0)
    idx = np.sort(rng.choice(train["X"].shape[0], size=a.calib, replace=False))
    calib = train["X"][idx].astype(np.float64)

    tensors, ops = E.graph_from_edge_unet(model)
    with torch.no_grad():
        ref = model(torch.from_numpy(calib[:64].astype(np.float32))).numpy()
    fold_err = float(np.abs(ref - E.run_float(tensors, ops, calib[:64])).max())
    im = E.quantize(tensors, ops, calib, meta={"name": "edge", "chans": list(model.chans),
                                               "trained_steps": int(ckpt.get("step", 0))})

    # Float vs integer on held-out windows (inputs quantised exactly as on the device).
    val = np.load(Path(a.data) / "val.npz")["X"][:512].astype(np.float64)
    xq = np.floor(np.clip(val, -12, 12) * (1 << E.IN_FB) + 0.5).astype(np.int16)
    yf = E.run_float(tensors, ops, xq.astype(np.float64) / (1 << E.IN_FB))
    yi = E.run_int(im, xq).astype(np.float64) / (1 << im.out_tensor.fb)
    err = yi - yf
    sat = float(np.mean(np.abs(E.run_int(im, xq)) >= 32767))
    report = {
        "params": im.n_params, "macs_per_window": im.macs, "arena_int16": im.arena_size,
        "arena_bytes": im.arena_size * 2, "weights_bytes": int(sum(op.w.size for op in im.ops if op.kind == E.OP_CONV)),
        "fractional_bits": {"input": E.IN_FB, "output": im.out_tensor.fb,
                            "tensors": [t.fb for t in im.tensors]},
        "bn_fold_max_abs_error": fold_err,
        "int_vs_float": {
            "wave_rms_error": float(np.sqrt(np.mean(err[:, :2] ** 2))),
            "wave_rms": float(np.sqrt(np.mean(yf[:, :2] ** 2))),
            "wave_snr_db": float(10 * np.log10(np.mean(yf[:, :2] ** 2) / np.mean(err[:, :2] ** 2))),
            "logit_rms_error": float(np.sqrt(np.mean(err[:, 2] ** 2))),
            "mask_decision_agreement": float(np.mean((yi[:, 2] > 0) == (yf[:, 2] > 0))),
            "output_saturation_fraction": sat,
        },
    }
    out = Path(a.out)
    (out / "metrics").mkdir(parents=True, exist_ok=True)
    E.save(im, out / "denoiser_edge_int.npz")
    E.write_c_header(im, a.header)
    # What belongs to this checkpoint travels with it: the float model and the training summary.
    onnx = Path(a.ckpt).with_suffix(".onnx")
    if onnx.exists():
        shutil.copyfile(onnx, out / "denoiser_edge.onnx")
    summary = Path(a.ckpt).parent / "metrics" / (Path(a.ckpt).stem + "_train.json")
    if summary.exists() and summary.resolve() != (out / "metrics" / summary.name).resolve():
        shutil.copyfile(summary, out / "metrics" / summary.name)
    (out / "metrics" / "denoiser_edge_export.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=1))
    print("wrote", out / "denoiser_edge_int.npz", "and", a.header)


if __name__ == "__main__":
    main()
