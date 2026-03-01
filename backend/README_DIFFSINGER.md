DiffSinger / DiffSpeech Integration Notes
=======================================

This file explains two practical routes to get English singing/speech output using the DiffSinger ecosystem.

1) Fine-tune DiffSinger on an English singing dataset (recommended for good singing)
--------------------------------------------------------------------------

Why: DiffSinger is designed for singing voice synthesis and usually trained on singing datasets (PopCS/OpenCpop). To get realistic English singing, fine-tune a checkpoint on an English singing dataset.

Steps (high-level):

- Clone a maintained DiffSinger repo (MoonInTheRiver or openvpi):

  git clone https://github.com/MoonInTheRiver/DiffSinger.git

- Prepare an English singing dataset in the repo's required format. Options:
  - NUS-48E: English singing dataset used in SVS research.
  - Prepare a small dataset from your own recordings: each sample needs audio, aligned lyrics and ideally F0/MIDI annotations.

- Create a Python env and install requirements (GPU strongly recommended):

  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements_3090.txt  # or requirements_2080.txt depending on GPU

- Convert or place your dataset under the repo's data/processed/<your_dataset> and update config files.

- Fine-tune from a pre-existing checkpoint (adapt the command to repo scripts/configs):

  cd DiffSinger
  python train.py --config configs/your_config.yaml --data_dir data/processed/your_dataset --output_dir exp/english_finetune --resume checkpoints/pretrained.pth

- After training finishes, run the repo inference script to synthesize lyrics + F0/MIDI (see repo's docs for formats):

  python inference.py --checkpoint exp/english_finetune/best.pth --lyrics_file inputs/lyrics.txt --midi inputs/score.mid --output output.wav

Notes & resources:
- Fine-tuning still requires a GPU and non-trivial VRAM (ideally 24GB+ depending on model size).
- The official repos include configs and scripts for preprocessing audio and extracting F0; follow them closely.
- License: check the checkpoint and repo license. Some community checkpoints may be CC-BY-NC or similar.

2) Use DiffSpeech (LJSpeech) for English TTS (speech, not singing)
-----------------------------------------------------------

Why: If you need English spoken output (not realistic singing), DiffSpeech models trained on LJSpeech provide high-quality English TTS and are often easier to run.

Quick start:

- Clone DiffSinger (which contains DiffSpeech scripts) or a DiffSpeech repo.

  git clone https://github.com/MoonInTheRiver/DiffSinger.git

- Install env & requirements (TTS may need different dependencies):

  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt

- Run TTS inference (example command — adjust to the repo's inference script name):

  python inference_tts.py --checkpoint checkpoints/diffspeech_ljspeech.pth --text "This is a test of DiffSpeech." --output tts_output.wav

Notes:
- DiffSpeech produces natural speech; it will not sing with musical pitch unless the model was adapted for singing.
- Many public TTS checkpoints (LJSpeech) exist; check the repo releases or Hugging Face to download one.

Finding checkpoints and model cards
----------------------------------
- Hugging Face search: https://huggingface.co/models?search=diffsinger
- GitHub: https://github.com/MoonInTheRiver/DiffSinger and https://github.com/openvpi/DiffSinger

If you want me to proceed, I can:
- Inspect specific Hugging Face model pages and download a checkpoint if an English one exists.
- Add a small inference wrapper to this repo that calls the DiffSinger/ DiffSpeech inference script with your uploaded checkpoint and returns an MP3/WAV file.
- Prepare the dataset conversion script (NUS -> DiffSinger format) and the minimal config to start fine-tuning.
