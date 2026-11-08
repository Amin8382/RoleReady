import argparse
import json


def main():
    parser = argparse.ArgumentParser(description="RoleReady reproducible pipelines")
    parser.add_argument(
        "command", choices=["download", "prepare", "index", "evaluate-retrieval", "check-dagshub"]
    )
    args = parser.parse_args()
    if args.command == "download":
        from roleready.data import download_sources

        result = download_sources()
    elif args.command == "prepare":
        from roleready.data import prepare_data

        result = prepare_data()
    elif args.command == "index":
        from roleready.retrieval import build_index

        result = build_index()
    elif args.command == "evaluate-retrieval":
        from roleready.retrieval import evaluate_retrieval

        result = evaluate_retrieval()
    else:
        from roleready.integrations import check_dagshub

        result = check_dagshub()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
