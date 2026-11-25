# GitHub Profile Setup (`@itzstebin`)

This repository automatically generates and updates your **Aquarium**, **Title Sequence**, and **Repo Galaxy** GitHub Profile themes with custom animated SVGs stored in `assets/`.

## Preview & Switch Themes

1. Open `preview.html` in any browser to compare **Aquarium**, **Title Sequence**, and **Repo Galaxy** side by side.
2. To switch the active theme in `README.md` locally:
   ```bash
   python scripts/generate_profile.py --theme aquarium
   # or:
   python scripts/generate_profile.py --theme title-sequence
   python scripts/generate_profile.py --theme repo-galaxy
   ```
3. Or switch directly on GitHub:
   - Edit `active_theme` in `profile.config.json`, **or**
   - Go to **Actions → Auto-Update Profile README & SVGs → Run workflow** and choose your theme from the dropdown.

## How Automatic Updates Work

- `.github/workflows/update-profile.yml` runs every **6 hours** (and whenever you edit `profile.config.json`).
- It uses `GITHUB_TOKEN` to query GitHub's GraphQL API for your live public repositories, star counts, language shares, followers, and 52-week contribution calendar / streaks.
- It regenerates all SVGs under `assets/` and refreshes `README.md` + `themes/*/README.md` automatically.
- Your existing `profile-3d.yml` and `snake.yml` workflows remain intact and linked inside the collapsible section at the bottom of the README.

## Deploying to `github.com/itzstebin/itzstebin`

Copy or push these files into your `itzstebin/itzstebin` repository (keeping your existing `profile-3d-contrib/` directory if you already have it):

- `README.md`
- `profile.config.json`
- `scripts/generate_profile.py`
- `assets/`
- `themes/`
- `data/github_snapshot.json`
- `.github/workflows/update-profile.yml`
