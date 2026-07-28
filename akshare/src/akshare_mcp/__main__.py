from akshare_mcp.config import get_settings
from akshare_mcp.server import mcp


def main() -> None:
    settings = get_settings()
    mcp.run(transport=settings.transport)


if __name__ == "__main__":
    main()
