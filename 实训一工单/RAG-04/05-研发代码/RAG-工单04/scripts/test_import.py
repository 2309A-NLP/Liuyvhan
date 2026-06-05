try:
    import main
    print("OK - main module imported")
    print(f"Has app: {hasattr(main, 'app')}")
except Exception as e:
    print(f"ERROR: {e}")
