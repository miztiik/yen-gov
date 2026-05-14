# How to extract the ICED API passphrase

**Last Updated**: 2026-05-14

> Use this when the existing passphrase (`AHten@VP0W3R` as of 2026-05-14)
> stops decrypting and every `IcedClient.get()` raises
> `ICEDShapeError("AES decrypt/unpad failed …")`. Means a new bundle was
> shipped and the constant rotated. Should take ~5 minutes.

## Pre-requisite

The bundle hash changes each build. Find the current one:

```powershell
# Open https://iced.niti.gov.in in any browser, view-source the homepage,
# and grep for `main.<hash>.js`. Or:
Invoke-WebRequest "https://iced.niti.gov.in/" `
  -UseBasicParsing |
  Select-Object -ExpandProperty Content |
  Select-String -Pattern 'main\.[0-9a-f]+\.js' -AllMatches |
  ForEach-Object { $_.Matches.Value } | Select-Object -Unique
```

That gives you the current bundle filename, e.g. `main.<hash>.js`.

## Recipe

1. **Download the bundle** (it is ~11 MB, public, no auth):

   ```powershell
   $hash = "<from step 0>"
   Invoke-WebRequest "https://iced.niti.gov.in/$hash" `
     -OutFile ".runtime/raw/iced/_bundle/$hash"
   ```

2. **Grep for the key constant**. The pattern has been stable across
   builds: an object literal with a `KEY:` field whose value is a short
   ASCII string near the end of the bundle (the env config module is
   one of the last things minified).

   ```powershell
   $bundle = Get-Content -Raw -Encoding Byte ".runtime/raw/iced/_bundle/$hash"
   $text = [System.Text.Encoding]::UTF8.GetString($bundle)
   # All quoted KEY: assignments
   [regex]::Matches($text, 'KEY:"([^"]{6,32})"') |
     ForEach-Object { $_.Groups[1].Value } |
     Select-Object -Unique
   ```

   You should get one short string. That is the new passphrase.

3. **Verify it decrypts a known endpoint** (use the test probe; it
   refuses to overwrite the production constant):

   ```powershell
   python tools/iced_decrypt_probe.py --key "<new passphrase>"
   ```

   If `/websiteLastUpdated` decodes to JSON containing `updated_at`,
   you have the right key.

4. **Update the constant** in
   `backend/yen_gov/sources/iced_common/crypto.py`:

   ```python
   PASSPHRASE: bytes = b"<new passphrase>"
   ```

   And add a one-line entry to its module docstring noting the
   rotation date and the bundle hash that introduced it.

5. **Re-run the iced_state_wise tests** — they include a round-trip
   test that catches both the encrypt and decrypt sides:

   ```powershell
   cd backend
   python -m pytest tests/test_sources_iced_state_wise.py -q
   ```

6. **Commit** as a single small change:

   ```text
   chore(iced): rotate ICED API passphrase to <new> (bundle <hash>)
   ```

## Why this works (and why it always will, until it doesn't)

The ICED Angular bundle decrypts every API response client-side. To do
that, the passphrase must be present in the bundle in plaintext (or in
something equivalent — a derived key, an obfuscated string with a
plaintext deobfuscator, etc.). All the bundle can do to slow us down is
*how* the passphrase is stored:

| Storage form | What we'd do |
| --- | --- |
| Plain `KEY:"..."` (today)         | regex extract (this doc). |
| Concatenated chunks (`a + b + c`) | grep for the call site of `AES.decrypt(...)` and read the constant assembled at runtime. |
| Obfuscated via a deobfuscator     | Run the bundle in `node`, monkey-patch `CryptoJS.AES.decrypt` to log its second argument, fetch any endpoint, read the log. |
| WebCrypto with key in IndexedDB   | Open the dashboard once in a real browser, dump the key from DevTools → Application → IndexedDB. |

None of these are "security" — every one of them ends with the key in
our hands within ten minutes. The reason this is OK is the data is
already public; ICED ships the encryption key to every browser that
asks. We document the rotation so future maintainers don't waste a day
thinking the decrypt code is broken.

## What we **don't** do

- We do **not** automate the captcha-gated download form
  (`/sendEmail`, `/validateRecaptcha`). That is a real anti-abuse
  control — it exists to stop bulk email-spamming, not to gate the
  data — and we respect it.
- We do **not** bypass any CDN-level rate limit, IP block, or other
  active defence ICED might add. If they ever ship one, we slow down
  or stop.

## See also

- [docs/architecture/backend/sources-iced-api.md](../architecture/backend/sources-iced-api.md) — full protocol writeup, why obfuscation ≠ security.
- [`backend/yen_gov/sources/iced_common/crypto.py`](../../backend/yen_gov/sources/iced_common/crypto.py) — the live constant + decryption code.
- [`tools/iced_decrypt_probe.py`](../../tools/iced_decrypt_probe.py) — standalone verification probe.
