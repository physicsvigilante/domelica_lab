# Publishing verified experiments

The publication workflow makes the existing self-contained viewers available through GitHub Pages. It copies the exact HTML files that passed browser verification; it does not regenerate simulation data during publication.

## One-time repository setup

In the repository's **Settings → Pages → Build and deployment**, choose **GitHub Actions** as the source. GitHub requires a signed-in repository administrator or maintainer to enable this setting. The normal workflow token cannot enable Pages for a repository.

The expected default site address is `https://physicsvigilante.github.io/domelica_lab/`. Treat it as available only after the **Publish Verified Lab** deployment has succeeded and the live page has been checked.

## Select a release

`site/release.json` names one immutable source revision and its successful **Native Modelica Lab** run. Each viewer entry names its HTML file, provenance manifest, browser report, and expected SHA-256. The initial selection is the accepted M2 run `44296447354`, source `77cb0d4529411c6f721f6ae74bb1009491cdf926`.

The publisher checks the run's repository, workflow path, source revision, completion, and success before downloading artifacts. It then requires agreement among the selected HTML hash, native provenance, browser report, and selected source/run. Failed browser steps, unexpected errors, and unexpected requests stop publication.

To update the public examples, review a new successful native/browser run, update this explicit release manifest, and merge that release selection. The publication workflow runs on changes to its own workflow, site sources, or site builder on `main`; it can also be run manually. It never publishes a pull request automatically.

## Outputs

- `index.html`: links to the selected experiments and offline downloads.
- Original verified viewer HTML, provenance, and browser reports.
- `publication.json`: selected source/run and hashes of all published files.

GitHub Actions artifacts must still be within their retention period when publishing. Once deployed, the site contains the viewer bytes directly; visiting it does not depend on an Actions artifact download or a GitHub login.

The graphics acceptance scope remains that of the original browser run. Serving the files over HTTPS does not turn recorded playback into live parameter-driven simulation or change the supported WebGL2 requirements.
