# Halo CLI Tools

CLI tools executed via subprocess, following the `halo-stack/cli_tools` convention.

## Structure

```
cli_tools/
├── config/config.json                             # root layered config
├── helper/config_loader.py                        # layered JSON config loader
├── skills.md                                       # root catalog with {{include}} directives
└── tools/
    └── image_model_routing/
        ├── config/config.json
        ├── common.py                               # image detection + token estimation
        ├── model_cards.py                          # vision-capable model registry
        ├── router.py                               # hard-filter + weighted-score routing engine
        ├── image_model_routing.py                  # CLI entry point
        └── image_model_routing_skill.md            # tool documentation for LLM/agent consumption
```

## Rules

- Tools always print JSON to stdout on success, JSON to stderr + `sys.exit(1)` on failure.
- CLI flags use `--kebab-case`, mapped to `snake_case` python args.
- Tool directory name must match the `.py` and `_skill.md` filenames.
- Only list config settings the tool actually reads.

## Testing a tool standalone

```bash
cd cli_tools
python tools/image_model_routing/image_model_routing.py --input-file scan.png
```
