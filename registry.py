"""Backward-compatible entry point – delegates to the app package.

Tests and external code that do ``from registry import app`` will continue
to work because this module exposes an ``app`` attribute created by the
application factory in ``app/__init__.py``.
"""
import os
from app import create_app

app = create_app()



if __name__ == '__main__':
    from app.config import DEFAULT_PORT

    port = int(os.environ.get('PORT', DEFAULT_PORT))
    cert_dir = os.environ.get('CERT_DIR')

    if cert_dir:
        cert_path = os.path.join(cert_dir, "fullchain.pem")
        key_path = os.path.join(cert_dir, "privkey.pem")

        if os.path.exists(cert_path) and os.path.exists(key_path):
            app.run(
                ssl_context=(cert_path, key_path),
                host='0.0.0.0',
                port=port
            )
        else:
            print("Certificate files not found. Running without SSL...")
            app.run(host='0.0.0.0', port=port)
    else:
        print("No certificate directory specified. Running without SSL...")
        app.run(host='0.0.0.0', port=port)

