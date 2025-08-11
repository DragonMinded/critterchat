import argparse
import getpass
import os
import sys
from typing import Optional

from critterchat.data import Data, DBCreateException
from critterchat.config import Config, load_config
from critterchat.service import AttachmentService, EmoteService, EmoteServiceException


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


def downgrade_db(config: Config, tag: str) -> None:
    """
    Given a config pointing at a valid MySQL DB that's been created already, undoes any migrations down
    to the given tag.
    """

    data = Data(config)
    data.downgrade(tag)
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


def create_user(config: Config, username: str, password: Optional[str]) -> None:
    """
    Create a new user that logs in with username, and uses password to login. If the password is
    not provided at the CLI, instead prompts for a password interactively.
    """

    if not password:
        # Prompt for it at the CLI instead.
        password1 = getpass.getpass(prompt="Password: ")
        password2 = getpass.getpass(prompt="Password again: ")
        if password1 != password2:
            raise CommandException("Passwords do not match!")
        password = password1

    data = Data(config)

    existing_user = data.user.from_username(username)
    if existing_user:
        raise CommandException("User already exists in the database!")

    new_id = data.user.create_account(username, password)
    if not new_id:
        raise CommandException("User could not be created!")
    print(f"User created with user ID {new_id}")

    data.close()


def change_user_password(config: Config, username: str, password: Optional[str]) -> None:
    """
    Given an existing user that logs in with username, update their password to the provded password.
    If the password is not provided at the CLI, instead prompts for a password interactively.
    """

    if not password:
        # Prompt for it at the CLI instead.
        password1 = getpass.getpass(prompt="Password: ")
        password2 = getpass.getpass(prompt="Password again: ")
        if password1 != password2:
            raise CommandException("Passwords do not match!")
        password = password1

    data = Data(config)

    existing_user = data.user.from_username(username)
    if not existing_user:
        raise CommandException("User does not exist in the database!")

    data.user.update_password(existing_user.id, password)
    print(f"User with ID {existing_user.id} updated with new password")

    data.close()


def list_emotes(config: Config) -> None:
    """
    List all of the custom emotes enabled on this network right now.
    """

    data = Data(config)
    emoteservice = EmoteService(config, data)
    emotes = emoteservice.get_all_emotes()
    names = sorted([e for e in emotes])
    for name in names:
        print(f"{name}")


def add_emote(config: Config, alias: Optional[str], filename_or_directory: str) -> None:
    """
    Given a filename or a directory, and optionally an alias, add emotes to the system.
    """

    data = Data(config)
    emoteservice = EmoteService(config, data)
    attachmentservice = AttachmentService(config, data)

    if os.path.isdir(filename_or_directory):
        if alias:
            raise CommandException("Cannot provide an alias when importing an entire directory!")

        # Add all files in this directory.
        for filename in os.listdir(filename_or_directory):
            alias, ext = os.path.splitext(filename)
            if ext.lower() not in {".png", ".gif", ".jpg", ".jpeg", ".webp"}:
                print(f"Skipping {filename} because it is not a recognized type!")

            full_file = os.path.join(filename_or_directory, filename)
            content_type = attachmentservice.get_content_type(full_file)
            with open(full_file, "rb") as bfp:
                emotedata = bfp.read()

            try:
                emoteservice.add_emote(alias, content_type, emotedata)
                print(f"Emote added to system with alias '{alias}'")
            except EmoteServiceException:
                print(f"Emote with alias '{alias}' not added to system")

    else:
        content_type = attachmentservice.get_content_type(filename_or_directory)
        with open(filename_or_directory, "rb") as bfp:
            emotedata = bfp.read()

        if not alias:
            alias = os.path.splitext(os.path.basename(filename_or_directory))[0]

        try:
            emoteservice.add_emote(alias, content_type, emotedata)
            print(f"Emote added to system with alias '{alias}'")
        except EmoteServiceException as e:
            raise CommandException(str(e))


def drop_emote(config: Config, alias: str) -> None:
    """
    Given an alias of an existing emote, drop it from the network.
    """

    data = Data(config)
    emoteservice = EmoteService(config, data)
    try:
        emoteservice.drop_emote(alias)
        print(f"Emote with alias '{alias}' removed from system")
    except EmoteServiceException as e:
        raise CommandException(str(e))


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

    downgrade_parser = database_commands.add_parser(
        "downgrade",
        help="unapply migrations to a specific tag",
        description="Unapply migrations to a specific tag.",
    )
    downgrade_parser.add_argument(
        "-t",
        "--tag",
        required=True,
        type=str,
        help="tag that we should downgrade to",
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
        default=None,
        type=str,
        help="password that the user will use to login with",
    )

    # Only a few params for this one
    change_password_parser = user_commands.add_parser(
        "change_password",
        help="change password for a user that can log in",
        description="Change password for a user that can log in.",
    )
    change_password_parser.add_argument(
        "-u",
        "--username",
        required=True,
        type=str,
        help="username that the user uses to login with",
    )
    change_password_parser.add_argument(
        "-p",
        "--password",
        default=None,
        type=str,
        help="password that the user uses to login with",
    )

    # Another subcommand here.
    emote_parser = commands.add_parser(
        "emote",
        help="modify custom emotes on the network",
        description="Modify custom emotes on the network.",
    )
    emote_commands = emote_parser.add_subparsers(dest="emote")

    # No params for this one
    emote_commands.add_parser(
        "list",
        help="list all custom emotes",
        description="List all custom emotes.",
    )

    # A few params for this one
    addemote_parser = emote_commands.add_parser(
        "add",
        help="add a custom emote",
        description="Add a custom emote.",
    )
    addemote_parser.add_argument(
        "-a",
        "--alias",
        type=str,
        help="alias to use for the emote you're adding, containing only alphanumberic characters, dashes and underscores",
    )
    addemote_parser.add_argument(
        "-f",
        "--file",
        type=str,
        required=True,
        help="file of the emote you're adding, and the name of the emote (without extension) if no alias is provided",
    )

    # A few params for this one
    dropemote_parser = emote_commands.add_parser(
        "drop",
        help="drop a custom emote",
        description="Drop a custom emote.",
    )
    dropemote_parser.add_argument(
        "-a",
        "--alias",
        type=str,
        required=True,
        help="alias of the emote you're dropping, containing only alphanumberic characters, dashes and underscores",
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
            elif args.database == "downgrade":
                downgrade_db(config, args.tag)
            else:
                raise CLIException(f"Unknown database operation '{args.database}'")

        elif args.operation == "user":
            if args.user is None:
                raise CLIException("Unspecified user operation1")
            elif args.user == "create":
                create_user(config, args.username, args.password)
            elif args.user == "change_password":
                change_user_password(config, args.username, args.password)
            else:
                raise CLIException(f"Unknown user operation '{args.user}'")

        elif args.operation == "emote":
            if args.emote is None:
                raise CLIException("Unspecified emote operation1")
            elif args.emote == "list":
                list_emotes(config)
            elif args.emote == "add":
                add_emote(config, args.alias, args.file)
            elif args.emote == "drop":
                drop_emote(config, args.alias)
            else:
                raise CLIException(f"Unknown emote operation '{args.emote}'")

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
