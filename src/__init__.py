try:
    from dotenv import load_dotenv
    # Load local .env for both app startup and standalone parser execution.
    load_dotenv()
except ImportError:
    pass

