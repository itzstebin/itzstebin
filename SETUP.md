# GitHub Profile Setup (`@itzstebin`)

This repository automatically generates and updates your **Wow Profile** GitHub Profile README with custom animated SVGs stored in `assets/wow-profile/`.

## Switch Themes Anytime

- **On GitHub:** Go to **Actions → Auto-Update Profile README & SVGs → Run workflow** and choose `wow-profile`, `repo-galaxy`, `aquarium`, or `title-sequence` from the dropdown.
- **Locally:**
  ```bash
  python scripts/generate_profile.py --theme wow-profile
  ```
  Pass `--all-themes` if you want to generate local previews (`themes/` and `preview.html`) for all themes at once.

## How Automatic Updates Work

- `.github/workflows/update-profile.yml` runs every **6 hours** (and whenever `profile.config.json` or `scripts/generate_profile.py` changes).
- It uses `GITHUB_TOKEN` to query GitHub's GraphQL API for your live public repositories, creation/push dates, star counts, language shares, followers, avatar ASCII portrait, and 52-week contribution calendar / streaks.
- It regenerates the active theme SVGs under `assets/` and updates `README.md` automatically.
- Your existing `profile-3d.yml` and `snake.yml` workflows remain active and linked inside the collapsible section at the bottom of `README.md`.
