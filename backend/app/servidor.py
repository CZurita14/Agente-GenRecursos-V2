"""Entrada HTTP con proxy y registro crudo desactivados explícitamente."""
import argparse
import uvicorn


def main(argv=None):
    parser = argparse.ArgumentParser(description="API del generador de recursos")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("Puerto fuera de rango")
    uvicorn.run("app.api.aplicacion:crear_app", factory=True, host=args.host, port=args.port,
                proxy_headers=False, access_log=False)


if __name__ == "__main__":
    main()
