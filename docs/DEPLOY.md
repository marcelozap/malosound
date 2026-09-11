# Publish MaloSound.ai

The public address is https://malosound.ai. Vercel deploys the `master` branch of
`https://github.com/marcelozap/malosound.git`. Its configuration runs
`python3 tools/build_website.py` and serves only `build/`.

## Exact public deploy command

From a checkout containing the latest `origin/master`, with the intended website
changes reviewed and committed:

```sh
python3 tools/build_website.py
git diff --check
git push origin HEAD:master
```

The last command triggers the existing Vercel deployment. It publishes the
committed source, so uncommitted edits are not deployed. Commit only the intended
website changes; do not use a blanket `git add .` in the music workspace.
If the push is rejected because the remote advanced, fetch and inspect those
changes before integrating them. Do not force-push production.

After the deployment finishes, verify the title is “MaloSound — price, played
back.”, the two new image URLs load, and retired routes such as `/journal.html`,
`/content/trades.json`, `/content/trading-journal.json`, and
`/content/journal-index.json` return 404. A successful Git push alone does not
prove the deployment finished.

## Local preview

```sh
python3 tools/build_website.py
python3 -m http.server 4178 --bind 127.0.0.1 --directory build
```

Open http://127.0.0.1:4178/.

## Public boundary

The builder has five explicit public files: the homepage, its stylesheet, the
404 page, the artwork, and the approved cover for link previews. It validates
references, clears stale output, and copies only that allowlist. It does not
read trading records, generate journal pages, fetch audio, or require a model,
data-feed account, API key, or scheduled job.

Raw trade-log paths are gitignored. The existing tracked trading journal was
removed from the Git index without deleting its local file. This does not
rewrite earlier Git history. Old editorial and research source is retained
outside the public build.

## Current release scope

This is the new visual identity and project-description release requested on
September 11, 2026. The generated artwork is brand artwork, not a plotted session.
The page describes the audiovisual generator as in development; it does not
claim that automatic session generation or voice playback is running.

`.openai/hosting.json` identifies the existing private Sites preview. Deploying
that preview does not update `malosound.ai` or change its DNS. The public command
above remains the deployment path for the custom domain.
