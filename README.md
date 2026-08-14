<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:6D28D9,100:06B6D4&height=250&section=header&text=Hi%20There,%20I'm%20Stebin%20S%20👋&fontSize=42&fontColor=ffffff&animation=fadeIn&fontAlignY=35&desc=Building%20things%20with%20code%20•%20Always%20learning&descAlignY=55&descSize=18" width="100%"/>

<a href="https://github.com/Stebin777">
  <img src="https://readme-typing-svg.demolab.com/?lines=Welcome+to+my+GitHub+profile!;I+love+Python+%26+building+cool+projects;Always+learning+something+new;Let's+build+something+great+together!&font=Fira%20Code&center=true&width=550&height=50&color=06B6D4&vCenter=true&size=24&pause=1200"/>
</a>

<br/>

<img src="https://komarev.com/ghpvc/?username=Stebin777&label=Profile%20Views&color=6D28D9&style=for-the-badge" alt="profile views"/>
&nbsp;
<a href="https://github.com/Stebin777?tab=followers"><img src="https://img.shields.io/github/followers/Stebin777?label=Followers&style=for-the-badge&color=06B6D4" alt="followers"/></a>

<br/><br/>

<a href="https://stebin777.github.io/portfolio/">
  <img src="https://img.shields.io/badge/🚀_View_my_3D_Portfolio-7C5CFC?style=for-the-badge&logoColor=white" alt="3D Portfolio"/>
</a>

<sub>↳ full interactive 3D page (tilt card, flip cartridge, live stats) — link goes live once you deploy it, see setup note below</sub>

</div>

<br/>

## 🧑‍💻 About Me

- 🎯 Currently sharpening my skills in **Python**
- 🌱 Learning something new every day and building small projects to prove it
- 🎮 Check out my game **[Guess-the-Number-Game](https://github.com/Stebin777/Guess-the-Number-Game)** — a fun little Python project
- 💬 Ask me about Python basics, game logic, or anything I'm currently learning
- ⚡ Fun fact: every commit is a step closer to something awesome

<br/>

## 🛠️ Tech Stack

<div align="center">

<img src="https://skillicons.dev/icons?i=python,git,github,vscode,html,css,js&theme=dark" />

</div>

<br/>

## 📊 GitHub Stats

<div align="center">

<img src="https://github-readme-stats.vercel.app/api?username=Stebin777&show_icons=true&theme=tokyonight&hide_border=true&count_private=true&include_all_commits=true" height="165"/>
<img src="https://github-readme-streak-stats.herokuapp.com/?user=Stebin777&theme=tokyonight&hide_border=true" height="165"/>

<img src="https://github-readme-stats.vercel.app/api/top-langs/?username=Stebin777&layout=compact&theme=tokyonight&hide_border=true&langs_count=8" height="165"/>

</div>

<br/>

## 🔥 Contribution Graph

<div align="center">

<img src="https://github-readme-activity-graph.vercel.app/graph?username=Stebin777&theme=tokyo-night&hide_border=true" width="95%"/>

</div>

<br/>

## 🐍 Contribution Snake (animated)

<div align="center">

<img src="https://raw.githubusercontent.com/Stebin777/Stebin777/output/github-contribution-grid-snake-dark.svg" width="95%"/>

</div>

> ⚠️ The snake animation above only shows up **after** you add the GitHub Action below to a repo named exactly `Stebin777` (your special profile repo). See the setup steps at the bottom of this file.

<br/>

## 🏆 Trophies

<div align="center">

<img src="https://github-profile-trophy.vercel.app/?username=Stebin777&theme=darkhub&no-frame=true&row=1&column=6" />

</div>

<br/>

## 📫 Connect With Me

<div align="center">

<a href="https://github.com/Stebin777"><img src="https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white"/></a>

</div>

<br/>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:06B6D4,100:6D28D9&height=120&section=footer"/>

</div>

<!--
================================================================
 SETUP GUIDE — how to make this fully "3D" / animated on GitHub
================================================================

1) CREATE THE SPECIAL PROFILE REPO
   - Create a new PUBLIC repository named EXACTLY: Stebin777
   - Add this file as README.md in that repo's root.
   - GitHub will auto-display it on your profile page.

1b) DEPLOY THE REAL 3D SITE (the "🚀 View my 3D Portfolio" button above)
   - README files on GitHub cannot run custom CSS/JS, so the fully interactive
     3D page (tilt badge, flip cartridge, starfield) has to live as its own
     site — this button just links out to it.
   - Create a new PUBLIC repository named: portfolio
   - Upload the 3 files from the 3D site folder to its root:
       index.html, style.css, script.js
   - Go to: Settings > Pages > Build and deployment > Source > "Deploy from a
     branch" > Branch: main / (root) > Save
   - After a minute your site is live at: https://stebin777.github.io/portfolio/
     (this already matches the button link above — no edit needed if you use
     "portfolio" as the repo name; otherwise update the URL in this README)

2) ENABLE THE ANIMATED CONTRIBUTION SNAKE
   - In the Stebin777 repo, go to: Settings > Secrets and variables > Actions
     (no secrets needed for the basic version)
   - Create a file at: .github/workflows/snake.yml with this content:

   name: generate snake
   on:
     schedule:
       - cron: "0 */6 * * *"
     workflow_dispatch: {}
     push:
       branches: [ main ]

   permissions:
     contents: write

   jobs:
     generate:
       runs-on: ubuntu-latest
       steps:
         - uses: Platane/snk/svg-only@v3
           with:
             github_user_name: Stebin777
             outputs: |
               dist/github-contribution-grid-snake.svg
               dist/github-contribution-grid-snake-dark.svg?palette=github-dark
         - uses: crazy-max/ghaction-github-pages@v4
           with:
             target_branch: output
             build_dir: dist
           env:
             GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

   - Run the workflow once manually (Actions tab > generate snake > Run workflow).
   - After it runs, the snake image URL in this README will start working.

3) CUSTOMIZE
   - Swap "Stebin777" text/links if you rename your account.
   - Edit the typing-SVG "lines=" text to change the animated intro messages.
   - Change theme= values (tokyonight, radical, dracula, gruvbox, etc.) on the
     stats/streak/activity-graph/trophy images to restyle everything at once.
   - Add real project cards by copying the GitHub Stats block and pointing
     repo-specific cards at your other repositories.

4) WHY IT'S "3D" / TRENDING
   - Wave header/footer (capsule-render) for a layered, animated look
   - Typing SVG for a live animated tagline
   - Skill icon strip, live stats, streak stats, top languages
   - Animated contribution snake eating your commit graph
   - Trophy case + live profile view counter
   These are the same building blocks used in most trending/"3D" GitHub
   profile READMEs right now.
================================================================
-->
