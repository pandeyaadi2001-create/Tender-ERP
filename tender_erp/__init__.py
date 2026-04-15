"""Tender & Compliance Management Desktop Application.

See README.md and the product specification for the full feature set. This
package ships a PySide6 desktop GUI plus a headless CLI for scripting and
tests. Everything lives in a single SQLite database under the user's
application data directory; the password vault is encrypted at rest using
AES-256-GCM with an Argon2id-derived key.
"""

__version__ = "0.5.0"
