# Repo signer and CI usage

This repo uses GPG to sign `Release` and `InRelease` for the APT repo.

- Secrets to set in GitHub:
  - `GPG_PRIVATE_KEY`: ASCII-armored private key content
  - `GPG_PASSPHRASE`: passphrase for the key (if set)

Example import step for GitHub Actions:

```yaml
- name: Import GPG key
  env:
    GPG_PRIVATE_KEY: ${{ secrets.GPG_PRIVATE_KEY }}
    GPG_PASSPHRASE: ${{ secrets.GPG_PASSPHRASE }}
  run: |
    set -e
    echo "$GPG_PRIVATE_KEY" | gpg --batch --passphrase "$GPG_PASSPHRASE" --pinentry-mode loopback --import
    KEY_FPR=$(gpg --list-secret-keys --with-colons | awk -F: '/^sec/{print $5;exit}')
    echo "$KEY_FPR:6:" | gpg --import-ownertrust
    echo "Using key $KEY_FPR"
```

Remember to remove key material after use if you export it to files.

Cloudflare R2 publish (CI)
--------------------------
The release and nightly workflows can publish the generated APT repo to Cloudflare R2 instead of GitHub Pages. Provide these secrets/vars:

- `R2_ACCOUNT_ID` (secret): Cloudflare account ID
- `R2_ACCESS_KEY_ID` (secret): R2 access key id
- `R2_SECRET_ACCESS_KEY` (secret): R2 secret
- `R2_BUCKET` (secret): target bucket name
- `R2_PREFIX` (variable, optional): prefix/path within the bucket (default: `apt`)

CI uses AWS S3 compatible API:

```
aws s3 sync . s3://$R2_BUCKET/$R2_PREFIX \
  --endpoint-url https://$R2_ACCOUNT_ID.r2.cloudflarestorage.com --delete
```

Ensure the bucket (and optional prefix) is configured for public read (or served behind Cloudflare with appropriate rules). Clients will fetch:

- `https://<your-domain>/$R2_PREFIX/dists/<stable|nightly>/InRelease`
- `https://<your-domain>/$R2_PREFIX/pubkey.asc` (for keyring installation)
