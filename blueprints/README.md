# 🧩 Blueprint Library

Blueprints describe repeatable automation or creative workflows.  
Use JSON or YAML to encode inputs, prompts, and execution steps.

## Template
```yaml
name: example_task
version: 0.1.0
description: Short summary of the automation goal.
steps:
  - id: acquire_source
    action: download
    params:
      url: https://example.com
  - id: transform_audio
    action: ffmpeg
    params:
      args: "-i input.wav -filter:a atempo=1.1 output.wav"
```
