# Security & Defense Architecture
**AeroSense AI — Cybersecurity Specification**

---

## 1. Authentication & Cryptography

1. **Password Hashing**: Uses pure `bcrypt` with cryptographic salt (`bcrypt.gensalt()`) and automatic truncation protection at 72 bytes. Passwords are never stored in plain text.
2. **Stateless JWT Tokens**: Signed using `HMAC-SHA256` with strict expiration windows (default 7 days).
3. **Authorization Enforcement**: FastAPI dependency injection (`get_current_user`) verifies claims on private endpoints (Alert Rules, Saved Locations, User Profile). Unauthenticated access to private resources returns `401 Unauthorized`.

---

## 2. GenAI Prompt-Injection & Tool Execution Safeguards

1. **Backend-Controlled Execution Only**:
   The Google Gemini model cannot execute SQL queries, inspect server filesystems, or invoke unvetted APIs. The model can only request tools declared in `AEROSENSE_TOOLS`. The FastAPI backend rigorously validates arguments before execution.
2. **Prompt Sanitization**:
   User input strings are sanitized, regex-normalized, and capped at 2,000 characters to prevent token-exhaustion denial of service and system prompt override attempts.
3. **Medical Disclaimer Enforcement**:
   The system instruction forbids individualized medical diagnoses, restricting outputs to outdoor environmental risk ratings and standard public health guidance.
4. **Key Isolation**:
   `GEMINI_API_KEY` and `OPENAQ_API_KEY` exist exclusively within backend environment variables and are never transmitted to or visible on the frontend client.

---

## 3. Web & Network Security Headers

AeroSense AI middleware injects strict defense headers on all HTTP responses:
- `X-Content-Type-Options: nosniff`: Prevents MIME-type sniffing attacks.
- `X-Frame-Options: DENY`: Blocks clickjacking and iframe framing.
- `X-XSS-Protection: 1; mode=block`: Mitigates legacy reflective XSS attacks.
- `CORS Allowlisting`: Restricted to trusted frontends and explicit development origins.
