from dyndns_nfsn.web import create_app

app = create_app()

if __name__ == '__main__':
    import argparse

    from dyndns_nfsn.main import main

    parser = argparse.ArgumentParser(description="Run the ddns service scheduler and/or web app")
    parser.add_argument(
        "--no-web",
        action="store_true",
        help="Run only the scheduler loop and do not start Flask built-in web server",
    )
    args = parser.parse_args()

    main(run_web=not args.no_web)
