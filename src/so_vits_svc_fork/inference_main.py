from __future__ import annotations

from logging import getLogger
from pathlib import Path
from typing import Literal

import librosa
import numpy as np
import soundfile
import torch

from .inference.infer_tool import RealtimeVC, RealtimeVC2, Svc

LOG = getLogger(__name__)


def infer(
    *,
    # paths
    input_path: Path | str,
    output_path: Path | str,
    model_path: Path | str,
    config_path: Path | str,
    # svc config
    speaker: str,
    cluster_model_path: Path | str | None = None,
    transpose: int = 0,
    auto_predict_f0: bool = False,
    cluster_infer_ratio: float = 0,
    noise_scale: float = 0.4,
    # slice config
    db_thresh: int = -40,
    pad_seconds: float = 0.5,
    chunk_seconds: float = 0.5,
    absolute_thresh: bool = False,
    device: Literal["cpu", "cuda"] = "cuda" if torch.cuda.is_available() else "cpu",
):
    model_path = Path(model_path)
    output_path = Path(output_path)
    input_path = Path(input_path)
    config_path = Path(config_path)
    cluster_model_path = Path(cluster_model_path) if cluster_model_path else None
    svc_model = Svc(
        net_g_path=model_path.as_posix(),
        config_path=config_path.as_posix(),
        cluster_model_path=cluster_model_path.as_posix()
        if cluster_model_path
        else None,
        device=device,
    )

    audio, _ = librosa.load(input_path, sr=svc_model.target_sample)
    audio = svc_model.infer_silence(
        audio,
        speaker=speaker,
        db_thresh=db_thresh,
        pad_seconds=pad_seconds,
        transpose=transpose,
        auto_predict_f0=auto_predict_f0,
        cluster_infer_ratio=cluster_infer_ratio,
        noise_scale=noise_scale,
        chunk_seconds=chunk_seconds,
        absolute_thresh=absolute_thresh,
    )

    soundfile.write(output_path, audio, svc_model.target_sample)


def realtime(
    *,
    # paths
    model_path: Path | str,
    config_path: Path | str,
    # svc config
    speaker: str,
    cluster_model_path: Path | str | None = None,
    transpose: int = 0,
    auto_predict_f0: bool = False,
    cluster_infer_ratio: float = 0,
    noise_scale: float = 0.4,
    # slice config
    db_thresh: int = -40,
    pad_seconds: float = 0.5,
    chunk_seconds: float = 0.5,
    # realtime config
    crossfade_seconds: float = 0.05,
    block_seconds: float = 0.5,
    version: int = 2,
    input_device: int | str | None = None,
    output_device: int | str | None = None,
    device: Literal["cpu", "cuda"] = "cuda" if torch.cuda.is_available() else "cpu",
):
    import sounddevice as sd

    model_path = Path(model_path)
    config_path = Path(config_path)
    cluster_model_path = Path(cluster_model_path) if cluster_model_path else None
    svc_model = Svc(
        net_g_path=model_path.as_posix(),
        config_path=config_path.as_posix(),
        cluster_model_path=cluster_model_path.as_posix()
        if cluster_model_path
        else None,
        device=device,
    )
    if version == 1:
        model = RealtimeVC(
            svc_model=svc_model,
            crossfade_len=int(crossfade_seconds * svc_model.target_sample),
        )
    else:
        model = RealtimeVC2(
            svc_model=svc_model,
        )

    # LOG all device info
    devices = sd.query_devices()
    LOG.info(f"Device: {devices}")
    if isinstance(input_device, str):
        input_device_candidates = [
            i for i, d in enumerate(devices) if d["name"] == input_device
        ]
        if len(input_device_candidates) == 0:
            LOG.warning(f"Input device {input_device} not found, using default")
            input_device = None
        else:
            input_device = input_device_candidates[0]
    if isinstance(output_device, str):
        output_device_candidates = [
            i for i, d in enumerate(devices) if d["name"] == output_device
        ]
        if len(output_device_candidates) == 0:
            LOG.warning(f"Output device {output_device} not found, using default")
            output_device = None
        else:
            output_device = output_device_candidates[0]
    if input_device is None or input_device >= len(devices):
        input_device = sd.default.device[0]
    if output_device is None or output_device >= len(devices):
        output_device = sd.default.device[1]
    LOG.info(
        f"Input Device: {devices[input_device]['name']}, Output Device: {devices[output_device]['name']}"
    )

    def callback(
        indata: np.ndarray,
        outdata: np.ndarray,
        frames: int,
        time: int,
        status: sd.CallbackFlags,
    ) -> None:
        LOG.debug(
            f"Frames: {frames}, Status: {status}, Shape: {indata.shape}, Time: {time}"
        )

        kwargs = dict(
            input_audio=indata.mean(axis=1),
            speaker=speaker,
            transpose=transpose,
            auto_predict_f0=auto_predict_f0,
            noise_scale=noise_scale,
            cluster_infer_ratio=cluster_infer_ratio,
            db_thresh=db_thresh,
            chunk_seconds=chunk_seconds,
        )
        if version == 1:
            kwargs["pad_seconds"] = pad_seconds
        outdata[:] = model.process(
            **kwargs,
        ).reshape(-1, 1)

    with sd.Stream(
        device=(input_device, output_device),
        channels=1,
        callback=callback,
        samplerate=svc_model.target_sample,
        blocksize=int(block_seconds * svc_model.target_sample),
    ):
        while True:
            sd.sleep(1)
