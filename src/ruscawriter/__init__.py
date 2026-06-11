"""RuscaWriter — editor di scrittura a tre colonne del progetto RuscaLinux."""
from .model import APP_NAME, APP_VERSION, APP_AUTHOR

__all__ = ["APP_NAME", "APP_VERSION", "APP_AUTHOR", "main"]


def main():
    """Punto di ingresso dell'applicazione."""
    from .editor import main as _main
    return _main()
