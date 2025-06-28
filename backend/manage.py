import argparse
import sys
from federateddergchat.data import Data, DBCreateException
from federateddergchat.config import Config, load_config


class CLIException(Exception):
    pass


class CommandException(Exception):
    pass


def create_db(config: Config) -> None:
    """
    Given a config pointing at a valid MySQL DB, initializes that DB by creating all required tables.
    """

    data = Data(config)
    data.create()
    data.close()


def upgrade_db(config: Config) -> None:
    """
    Given a config pointing at a valid MySQL DB that's been created already, runs any pending migrations
    that were checked in since you last ran create or migrate.
    """

    data = Data(config)
    data.upgrade()
    data.close()


def generate_migration(config: Config, message: str, allow_empty: bool) -> None:
    """
    Given some changes to the table definitions in the SQL files of this repo, and a config pointing
    at a valid MySQL DB that has previously been initialized and then upgraded to the base revision
    of the repo before modification, generates a migration that will allow a production instance to
    auto-upgrade their DB to mirror your changes.
    """

    data = Data(config)
    data.generate(message, allow_empty)
    data.close()


def create_user(config: Config, username: str, password: str) -> None:
    """
    Given a config pointing at a valid MySQL DB that's been created already, runs any pending migrations
    that were checked in since you last ran create or migrate.
    """

    data = Data(config)

    existing_id = data.user.from_username(username)
    if existing_id:
        raise CommandException("User already exists in the database!")

    new_id = data.user.create_account(username, password)
    if not new_id:
        raise CommandException("User could not be created!")
    print(f"User created with user ID {new_id}")

    data.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="A utility for administrating the DB.")
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="config.yaml",
        help="core configuration, used for determining what DB to connect to (defaults to config.yaml)",
    )
    commands = parser.add_subparsers(dest="operation")

    # Another subcommand here.
    database_parser = commands.add_parser(
        "database",
        help="modify backing DB for this network",
        description="Modify backing DB for this network.",
    )
    database_commands = database_parser.add_subparsers(dest="database")

    # No params for this one
    database_commands.add_parser(
        "create",
        help="create tables in fresh DB",
        description="Create tables in fresh DB.",
    )

    # Only a few params for this one
    generate_parser = database_commands.add_parser(
        "generate",
        help="generate migration from a DB and code delta",
        description="Generate migration from a DB and code delta.",
    )
    generate_parser.add_argument(
        "-m",
        "--message",
        required=True,
        type=str,
        help="message to use for auto-generated migration scripts, similar to a commit message",
    )
    generate_parser.add_argument(
        "-e",
        "--allow-empty",
        action='store_true',
        help="allow empty migration script to be generated (useful for creating data-only migrations)",
    )

    # No params for this one
    database_commands.add_parser(
        "upgrade",
        help="apply pending migrations to a DB",
        description="Apply pending migrations to a DB.",
    )

    # Another subcommand here.
    user_parser = commands.add_parser(
        "user",
        help="modify backing DB for this network",
        description="Modify backing DB for this network.",
    )
    user_commands = user_parser.add_subparsers(dest="user")

    # Only a few params for this one
    create_parser = user_commands.add_parser(
        "create",
        help="create a new user that can log in",
        description="Create a new user that can log in.",
    )
    create_parser.add_argument(
        "-u",
        "--username",
        required=True,
        type=str,
        help="username that the user will use to login with",
    )
    create_parser.add_argument(
        "-p",
        "--password",
        required=True,
        type=str,
        help="password that the user will use to login with",
    )

    args = parser.parse_args()

    config = Config()
    load_config(args.config, config)
    try:
        if args.operation is None:
            raise CLIException("Unuspecified operation!")

        elif args.operation == "database":
            if args.database is None:
                raise CLIException("Unuspecified database operation!")
            elif args.database == "create":
                create_db(config)
            elif args.database == "generate":
                generate_migration(config, args.message, args.allow_empty)
            elif args.database == "upgrade":
                upgrade_db(config)
            else:
                raise CLIException(f"Unknown database operation '{args.database}'")

        elif args.operation == "user":
            if args.user is None:
                raise CLIException("Unspecified user operation1")
            elif args.user == "create":
                create_user(config, args.username, args.password)
            else:
                raise CLIException(f"Unknown user operation '{args.user}'")

        else:
            raise CLIException(f"Unknown operation '{args.operation}'")
    except CLIException as e:
        print(str(e), file=sys.stderr)
        print(file=sys.stderr)
        parser.print_help(sys.stderr)
        sys.exit(1)
    except CommandException as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except DBCreateException as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
