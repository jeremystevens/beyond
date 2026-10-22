# Model settings reference

Recorded 2026-10-21 after an accidental welcome-preset change. CPU mode only.

| Model | CPU threads | Context | Cache | Thinking | Evidence |
|---|---:|---:|---|---|---|
| Qwen3-1.7B-Q8_0.gguf | 12 | 8192 | f16 | Off | Earlier saved model profile |
| Qwen3-4B-Q4_K_M.gguf | 6 | 2048 | f16 | Off | Current settings and engine log after the preset changes |

The original pre-change settings for the 4B model could not be recovered. Its row is a snapshot of the observed current configuration, not a verified original profile. The 1.7B values should not be described as the recovered 4B settings.

## Restore manually

1. Open Models and choose the intended model.
2. Expand Model settings (or use Settings > AI engine).
3. Enter the threads, context, cache and thinking values from the matching row and save.
4. Wait for the built-in model to reload before chatting.

Changing a welcome preset changes performance settings, not the model file. Keep current preserves the settings currently saved; it does not undo an earlier preset change. Choosing a different preset can overwrite the active model profile.

Keep this reference separate from live settings so future preset changes cannot overwrite it. Review this note when you deliberately choose a new configuration. No live settings were changed while creating this reference.
