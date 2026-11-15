"""PyTorch definition of the motion-artefact denoiser (training only).

A small 1-D U-Net over a 10.24 s window of both MAX30102 channels:

    input  (B, 2, 512): IR and red blood-volume signals, divided by the IR std
    output (B, 3, 512): clean IR, clean red (same scaling), artefact logit

Red and IR share one scale factor so the network sees, and must preserve,
their amplitude ratio (the SpO2 ratio of ratios). Motion moves both channels
with a ratio that differs from the arterial one; the network learns to use
that difference, which is the idea behind dual-wavelength motion rejection.
The dilated bottleneck gives every output sample a receptive field longer
than the window, so it can use the periodicity of the pulse across beats.
"""

from __future__ import annotations

import torch
from torch import nn
import torch.nn.functional as F


class ConvBlock(nn.Module):
    def __init__(self, c_in: int, c_out: int, k: int = 7, dilations=(1, 1)):
        super().__init__()
        layers = []
        c = c_in
        for d in dilations:
            layers += [nn.Conv1d(c, c_out, k, padding=d * (k - 1) // 2, dilation=d),
                       nn.BatchNorm1d(c_out), nn.GELU()]
            c = c_out
        self.body = nn.Sequential(*layers)
        self.skip = nn.Conv1d(c_in, c_out, 1) if c_in != c_out else nn.Identity()

    def forward(self, x):
        return self.body(x) + self.skip(x)


class DenoiseUNet(nn.Module):
    def __init__(self, in_ch: int = 2, out_ch: int = 3, chans=(16, 32, 48, 64), bottleneck: int = 64, k: int = 7):
        super().__init__()
        self.enc = nn.ModuleList()
        self.down = nn.ModuleList()
        c = in_ch
        for ch in chans:
            self.enc.append(ConvBlock(c, ch, k))
            self.down.append(nn.Conv1d(ch, ch, 4, stride=2, padding=1))
            c = ch
        self.mid = ConvBlock(c, bottleneck, k, dilations=(1, 2, 4, 8))
        self.up = nn.ModuleList()
        self.dec = nn.ModuleList()
        c = bottleneck
        for ch in reversed(chans):
            self.up.append(nn.ConvTranspose1d(c, ch, 4, stride=2, padding=1))
            self.dec.append(ConvBlock(2 * ch, ch, k))
            c = ch
        self.head = nn.Conv1d(c, out_ch, 1)

    def forward(self, x):
        skips = []
        for enc, down in zip(self.enc, self.down):
            x = enc(x)
            skips.append(x)
            x = down(x)
        x = self.mid(x)
        for up, dec, s in zip(self.up, self.dec, reversed(skips)):
            x = up(x)
            x = dec(torch.cat([x, s], dim=1))
        return self.head(x)


class EdgeBlock(nn.Module):
    """conv -> BN -> ReLU, repeated; no residual branch.

    The edge model is built from one operation only (convolution + bias +
    optional ReLU) plus average pooling and sample repetition, so that the
    integer inference engine in the firmware stays small and exact.
    """

    def __init__(self, c_in: int, c_out: int, k: int = 7, dilations=(1, 1)):
        super().__init__()
        layers = []
        c = c_in
        for d in dilations:
            layers += [nn.Conv1d(c, c_out, k, padding=d * (k - 1) // 2, dilation=d),
                       nn.BatchNorm1d(c_out), nn.ReLU()]
            c = c_out
        self.body = nn.Sequential(*layers)

    def forward(self, x):
        return self.body(x)


class EdgeUNet(nn.Module):
    """Small U-Net for on-device inference (ESP32-C3, no FPU).

    Same input/output contract as DenoiseUNet. Differences, all chosen for a
    simple fixed-point implementation: ReLU instead of GELU, average pooling
    instead of strided convolutions, sample repetition instead of transposed
    convolutions, no residual branches. With chans=(8, 16, 24, 32): ~97 k
    parameters and ~10 M multiply-accumulates per 10.24-s window.
    Decoder input order is [upsampled, skip] (the integer engine relies on it).
    """

    def __init__(self, in_ch: int = 2, out_ch: int = 3, chans=(8, 16, 24, 32), k: int = 7):
        super().__init__()
        self.chans = tuple(chans)
        self.enc = nn.ModuleList()
        c = in_ch
        for ch in chans:
            self.enc.append(EdgeBlock(c, ch, k))
            c = ch
        self.mid = EdgeBlock(c, c, k, dilations=(1, 2, 4, 8))
        self.dec = nn.ModuleList()
        for ch in reversed(chans):
            self.dec.append(EdgeBlock(c + ch, ch, k))
            c = ch
        self.head = nn.Conv1d(c, out_ch, 1)

    def forward(self, x):
        skips = []
        for enc in self.enc:
            x = enc(x)
            skips.append(x)
            x = F.avg_pool1d(x, 2)
        x = self.mid(x)
        for dec, s in zip(self.dec, reversed(skips)):
            x = torch.repeat_interleave(x, 2, dim=-1)
            x = dec(torch.cat([x, s], dim=1))
        return self.head(x)


def build_model(arch: str = "unet", chans=None) -> nn.Module:
    if arch == "unet":
        return DenoiseUNet() if chans is None else DenoiseUNet(chans=tuple(chans), bottleneck=chans[-1])
    if arch == "edge":
        return EdgeUNet() if chans is None else EdgeUNet(chans=tuple(chans))
    raise ValueError(f"unknown arch {arch!r}")


def ratio_loss(pred: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """|R_pred - R_true| with R = sum(red*ir)/sum(ir^2) over artefact-free samples.

    Keeps the red/IR amplitude ratio right, which a plain waveform loss
    under-weights because the red pulse is only ~0.4-1.0x the IR one.
    """
    w = 1.0 - mask
    def r(y):
        ir, red = y[:, 0], y[:, 1]
        ir = ir - (ir * w).sum(-1, keepdim=True) / w.sum(-1, keepdim=True).clamp_min(1)
        red = red - (red * w).sum(-1, keepdim=True) / w.sum(-1, keepdim=True).clamp_min(1)
        return (w * red * ir).sum(-1) / (w * ir * ir).sum(-1).clamp_min(1e-6)
    ok = (w.sum(-1) > 64).float()
    return ((r(pred) - r(target)).abs().clamp_max(1.0) * ok).sum() / ok.sum().clamp_min(1)


def denoiser_loss(out: torch.Tensor, target: torch.Tensor, mask: torch.Tensor):
    wave = out[:, :2]
    l_wave = F.l1_loss(wave, target)
    l_der = F.l1_loss(wave[..., 1:] - wave[..., :-1], target[..., 1:] - target[..., :-1]) * 4.0
    l_mask = F.binary_cross_entropy_with_logits(out[:, 2], mask)
    l_r = ratio_loss(wave, target, mask)
    total = l_wave + l_der + 0.2 * l_mask + 0.5 * l_r
    return total, {"wave": l_wave.item(), "deriv": l_der.item(), "mask": l_mask.item(), "ratio": l_r.item()}
