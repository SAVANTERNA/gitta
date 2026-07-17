# deb-builder
Skeleton for single binary (.deb)

## Principer
> [!TIP]
> One binary: bygg en enda körbar artefakt per målplattform. Paketeringen (deb) innehåller bara binären + metadata (manpage, systemd, config exempel).
> Reproducerbar build: bygg i en kontrollerad miljö (Docker / CI runner). Inget beroende på dev-maskin.
> Automatisera: CI bygger artefakter, signerar, och uppdaterar APT-repo automatiskt.

> [!WARNING]
> Säker publicering: signera .deb (optionellt) och alltid signera APT Release med GPG; public key distribueras via *-archive-keyring paket eller README.

> [!IMPORTANT]
> Simplicity first: använd goreleaser/nfpm eller fpm beroende på vad du föredrar — men välj ett verktyg och håll dig till det.

```
project/
├── .github/
│   └── workflows/
│       ├── ci.yml            # build + test
│       └── release.yml       # build + package + publish (goreleaser)
├── build/
│   ├── docker/               # Dockerfile(s) för reproducible build
│   ├── pack-deb.sh          # helper script (calls nfpm/fpm/dpkg-deb)
│   └── publish-apt.sh       # uploader / repo-updater
├── packaging/
│   ├── debian/              # optional if using dpkg-buildpackage
│   │   ├── control
│   │   ├── changelog
│   │   └── install
│   └── repo-signer/         # reprepro/aptly config or apt-ftparchive config
├── scripts/                 # small dev utilities (install-local, lint)
├── dist/                    # CI artifacts (.deb, tar.gz)  (gitignored)
├── src/ OR cmd/             # language-specific source (e.g. cmd/main or src/)
│   └── ...                  # your code / main entrypoint
├── assets/
│   ├── appname.1            # manpage
│   └── appname.service      # optional systemd unit
├── docs/
│   ├── README.md
│   └── APT_PUBLISH.md       # how to host the repo & key distribution
├── nfpm.yaml OR fpm.conf    # package config if using nfpm/fpm
├── .goreleaser.yml          # optional: create debs and build artifacts
├── Makefile
└── LICENSE
```

## APT Installation (Cloudflare R2)

Stable releases are published to Cloudflare R2 (public r2.dev). Add the repo and key:

1) Import the public key (preferred: keyring path; first-time bootstrap):

```
curl -fsSL https://pub-bb9a9de46d6b43c2aa928b0db39bc1e6.r2.dev/apt/pubkey.asc \
  | sudo tee /usr/share/keyrings/gitta-archive-keyring.asc >/dev/null
```

2) Add the apt source (stable):

```
echo "deb [signed-by=/usr/share/keyrings/gitta-archive-keyring.asc] \
  https://pub-bb9a9de46d6b43c2aa928b0db39bc1e6.r2.dev/apt stable main" | sudo tee /etc/apt/sources.list.d/gitta.list
sudo apt update
sudo apt install gitta
```

Nightly builds are available at `dists/nightly`:

```
echo "deb [signed-by=/usr/share/keyrings/gitta-archive-keyring.asc] \
  https://pub-bb9a9de46d6b43c2aa928b0db39bc1e6.r2.dev/apt nightly main" | sudo tee /etc/apt/sources.list.d/gitta-nightly.list
sudo apt update
```

Tip: We plan to provide a `gitta-archive-keyring` package; once available, replace the curl step with `apt install gitta-archive-keyring`.
\nOnce the repo is configured and the key is installed, you can switch to managing the key via the keyring package:

Once the repo is configured and the key is installed, you can switch to managing the key via the keyring package:

sudo apt install gitta-archive-keyring
```

## TUI (Text User Interface)

Start the TUI:

```
gitta tui
```

If you don't have Textual installed, add the optional extra:

```
python -m pip install 'gitta[tui]'
```

Key bindings in TUI:
- q: quit
- r: refresh
- s: switch to Status tab
- g: switch to Graph tab
- d: switch to Diff tab

Planned panels: staging, commit dialog, stash, undo, and tag bump.
