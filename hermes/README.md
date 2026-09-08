# Hermes wiring

Everything in this folder is the Hermes side of the project: the five agent profiles, the five skills, and the Kanban board they collaborate on.

## Install Hermes

```powershell
# Windows
iex (irm https://hermes-agent.nousresearch.com/install.ps1)
```

```bash
# macOS / Linux / WSL2
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

Then point it at a model:

```bash
hermes config set OPENROUTER_API_KEY <your key>
hermes model
hermes doctor
```

For the **in-process** runtime (`AIAgent` imported directly, which is what `cwt_ads.cli run` uses) you also need a source checkout, because Hermes does not publish a wheel:

```bash
python -m cwt_ads.cli setup-hermes          # clones into vendor/hermes-agent
cd vendor/hermes-agent && uv sync
# then add to .env:  HERMES_HOME=<that path>
```

## Profiles

`profiles/<name>/config.yaml` is the reference copy kept in the repo. `python -m cwt_ads.cli kanban bootstrap` creates the live profiles under `~/.hermes/profiles/`.

| Profile | Role | Toolsets | Temp |
|---|---|---|---|
| `cwt_ads_manager` | Ads Manager | web, files | 0.3 |
| `cwt_insight_miner` | Creative Strategist | files | 0.6 |
| `cwt_market_researcher` | Market Researcher | web, files | 0.4 |
| `cwt_script_writer` | Creative Director | files | 0.9 |
| `cwt_video_director` | Video Director | terminal, files, web | 0.3 |

The temperatures are deliberate: the Ads Manager is scoring evidence and the Creative Director is writing a film. They should not be the same agent at the same setting.

## Skills

One `SKILL.md` per stage, following the Hermes format — frontmatter with `required_environment_variables`, then *When to Use*, *Quick Reference*, *Procedure*, *Pitfalls*, *Verification*. Regenerate them all with:

```bash
python hermes/skills/_generate.py
```

They are generated from one table so the five stay consistent with each other and with `config/pipeline.yaml`. Edit `_generate.py`, not the Markdown.

Each skill ends with the same contract: complete with artifact paths in metadata, or **block** — never re-derive work that belongs to another agent.

## The board

```bash
python -m cwt_ads.cli kanban plan        # print every command, change nothing
python -m cwt_ads.cli kanban bootstrap   # init the board, create profiles + tasks
hermes kanban watch
hermes dashboard                         # Kanban tab
```

`kanban/board.yaml` documents the graph; `kanban/bootstrap.py` is a standalone entry point if you would rather not go through the CLI.

All five tasks share `--workspace dir:<repo>` so each agent can read the run folder the previous agent wrote into. That shared folder is the entire handoff protocol — which is why every stage can also load its inputs from disk, and why the in-process and board paths produce byte-identical artifacts.
