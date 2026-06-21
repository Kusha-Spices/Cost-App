#!/usr/bin/env python3
"""
Tiny static file server for Aetherion.

ES modules (the game's `import` statements) are blocked by browsers when a page
is opened directly from disk (file://). Serving over http:// fixes that.

Usage:
    python3 serve.py            # serves on http://localhost:8000
    python3 serve.py 5500       # serves on a custom port

Then open the printed URL in your browser.
"""
import http.server
import socketserver
import sys
import webbrowser

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000


class Handler(http.server.SimpleHTTPRequestHandler):
    # Make sure .js is served as a JS module type and disable caching while developing.
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
    }

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):  # quieter console
        pass


def main():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        url = f"http://localhost:{PORT}/"
        print("=" * 52)
        print("  AETHERION — local server running")
        print(f"  Open:  {url}")
        print("  Press Ctrl+C to stop.")
        print("=" * 52)
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
