# Trained models

Checkpoints are stored as `models/<name>.pt` (written by `kingisdead.rl.checkpoint.save_checkpoint`)
and used by the seat type `trained:<name>`. Names are lowercase `[a-z0-9_-]`, e.g. `models/ppo-2p-v1.pt`.
Scratch training output goes in `runs/` (git-ignored); only promoted models are committed here.
