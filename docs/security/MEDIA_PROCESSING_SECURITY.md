# Media Processing Security & Subprocess Hardening Guide

## 1. Threat Model & Security Invariants

Processing user-uploaded audio and video presents major attack vectors:
1. **Malicious File Uploads**: Polyglots, zip bombs, executable payloads disguised as media files.
2. **Command Injection**: Exploiting shell metacharacters in media filenames or metadata to execute arbitrary code.
3. **Information Disclosure & Secret Leaks**: Child processes inheriting database credentials or sensitive API keys via environment variables.
4. **Path Traversal / Cross-Tenant Access**: Manipulating asset IDs, output filenames, or download URLs to read/overwrite other tenants' files.
5. **Denial of Service**: Processing excessively large or infinite media streams that exhaust server CPU, GPU, or disk storage.

---

## 2. Hardened Subprocess Execution

All FFmpeg, FFprobe, Whisper, and Tesseract executions follow these zero-trust rules:

### A. Strict List-Based Arguments (No Shell)
Commands are built strictly as lists of string arguments:
```python
# SECURE: Executable and arguments isolated in array
cmd = [self.ffmpeg_path, "-y", "-i", input_path, "-vf", "scale=1080:1920", output_path]
proc = await asyncio.create_subprocess_exec(*cmd, ...)

# VULNERABILITY PREVENTED:
# Never uses `shell=True` or string interpolation `f"ffmpeg -i {input_path}"`
```

### B. Environment Variable Scrubbing
Child processes run in a sanitized environment that strips platform secrets:
```python
SENSITIVE_VARS = {
    "DATABASE_URL", "REDIS_URL", "SECRET_KEY", "JWT_SECRET_KEY",
    "API_KEY", "AWS_SECRET_ACCESS_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"
}
clean_env = {k: v for k, v in os.environ.items() if k not in SENSITIVE_VARS}
```

### C. Execution Timeouts & Termination
Every process has an enforced timeout (default 300 seconds). On timeout, the engine immediately terminates the process group via `proc.kill()` and releases resources.

---

## 3. Upload Validation & Path Containment

### A. Magic Byte MIME Verification
Uploaded files are verified by inspecting their header signatures against standard binary magic bytes:
- `video/mp4`: `ftyp` box signatures (`ftypisom`, `ftypmp42`, `ftypqt`).
- `audio/wav`: `RIFF....WAVEfmt ` signature.
- `image/png`: `\x89PNG\r\n\x1a\n` signature.
- Plain text, shell scripts, or binary executables (.exe, .sh) disguised with media extensions are rejected with HTTP 422.

### B. Non-User-Controlled Storage Keys
Uploaded files are stored using generated UUID-based filenames (`{uuid4().hex}.mp4`), stripping all client-supplied filenames and path characters.

### C. Tenant Root Containment
Every storage path is verified via `LocalStorageProvider._resolve_tenant_path()`. It calculates `os.path.commonpath([tenant_root, resolved_path])` and raises `PermissionError` if the path falls outside the tenant's root folder.

---

## 4. Download Token Cryptographic Verification

Streaming URLs require short-lived HMAC-SHA256 signed tokens:
```
Token Format: {tenant_id}:{media_id}:{user_id}:{expiration}:{hmac_sha256_signature}
```
1. Tokens expire after 15 minutes.
2. The endpoint verifies `hmac.compare_digest(provided_sig, expected_sig)`.
3. The token binds `tenant_id` and `media_id`; mismatched parameters return HTTP 403.
