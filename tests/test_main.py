import json
import os
from pathlib import Path
from unittest import SkipTest, TestCase

IS_CI = os.environ.get("GITHUB_ACTIONS", False)
IS_COLAB = os.getenv("COLAB_RELEASE_TAG", False)


class TestMain(TestCase):
    def test_import(self):
        import so_vits_svc_fork.cluster.train_cluster  # noqa
        import so_vits_svc_fork.inference_main  # noqa
        import so_vits_svc_fork.onnx_export  # noqa
        import so_vits_svc_fork.preprocess_flist_config  # noqa
        import so_vits_svc_fork.preprocess_hubert_f0  # noqa
        import so_vits_svc_fork.preprocess_resample  # noqa
        import so_vits_svc_fork.train  # noqa

    def test_infer(self):
        if IS_CI:
            raise SkipTest("Skip inference test on CI")
        from so_vits_svc_fork.inference_main import infer  # noqa

        # infer("tests/dataset_raw/44k/34j/1.wav", "tests/configs/config.json", "tests/logs/44k")

    def test_preprocess(self):
        from so_vits_svc_fork.preprocess_resample import preprocess_resample

        preprocess_resample("tests/dataset_raw/44k", "tests/dataset/44k", 44100)

    def test_preprocess_config(self):
        from so_vits_svc_fork.preprocess_flist_config import preprocess_config

        preprocess_config(
            "tests/dataset/44k",
            "tests/filelists/train.txt",
            "tests/filelists/val.txt",
            "tests/filelists/test.txt",
            "tests/configs/config.json",
        )

    def test_preprocess_hubert(self):
        if IS_CI:
            raise SkipTest("Skip preprocessing test on CI")
        from so_vits_svc_fork.preprocess_hubert_f0 import preprocess_hubert_f0

        preprocess_hubert_f0("tests/dataset/44k", "tests/configs/44k/config.json")

    def test_train(self):
        if not IS_COLAB:
            raise SkipTest("Skip training test on non-colab")
        # requires >10GB of GPU memory, can be only tested on colab
        from so_vits_svc_fork.train import train

        config_path = Path("tests/logs/44k/config.json")
        config_json = json.loads(config_path.read_text())
        config_json["train"]["epochs"] = 1
        config_path.write_text(json.dumps(config_json))
        train(config_path, "tests/logs/44k")
