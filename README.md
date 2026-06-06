# CritterChat

A web-based chat program that you can host yourself, providing direct messaging,
private group conversations and public rooms. Started as a middle finger to Discord
and now evolving slowly into its own thing. CritterChat focuses on ease of
experience over highly technical things like end-to-end encryption. As of right
now instances are standalone but I would like to implement some sort of
federation between instances that can be enabled or disabled per-instance.

## Feature List

 - Web frontend with both mobile and desktop support.
 - Public rooms with optional auto-join for new members.
 - Private group conversations with an invite system for adding members.
 - Direct messages between members on the instance.
 - Direct messages, private conversations and public rooms have an editable name and topic.
 - Member profile support with ability to view other chatters' profiles.
 - Custom emoji support controlled by the instance administrator.
 - Message reactions, with custom emoji support and multiple reactions per message.
 - Preferences for most appearance settings and optional notification sounds.
 - Image attachment support so images can be sent with messages.
 - Ability to spoiler a message or an attachment, alt text for attachments.
 - Various sign-up modes such as open registration, admin-approval and invite codes.
 - Integration with Mastodon's OAuth for account creation and member authentication.
 - Collects absolutely no personal information, contains no tracking code.
 - Not built with, enabled by or integrated with any generative AI.

## Wishlist

 - Message editing.
 - Message deleting.
 - Reply to message.
 - Now typing indicators.
 - Read receipts.
 - Pinned messages.
 - Sticker support.
 - Moderation tools for network admin (global mute, global ban, etc).
 - Moderation tools for individuals (block user, allow direct messages, etc.).
 - Emoji auto-categorization by prefix.
 - Arbitrary file attachments.
 - Sitewide CSS themeing with CSS moved to themes directory.
 - Per-chat CSS themeing for direct messages, private conversations and rooms.
 - Ability to set a personal nickname for a user that only you can see in a direct message or private conversation.
 - Port Myno's Pictochat over from PyStreaming, allow drawing and remixing.
 - Link auto-sanitization to remove tracking info.
 - Multi-account support in the web frontend.
 - Inter-instance direct messages and private conversations, inter-instance OIDC-based authentication.
 - REST API for bot integration, discord-compatible webhook support.

## Needed Help

If you're looking for something to contribute and something on this or the above
list sparks your interest we would be very grateful for a contribution! Please
get in touch so we can work out the direction you plan to take.

 - Containerization and simplifying deployment/updates.
 - UX design work and help with themes.
 - Accessibility help, audits and fixes.
 - Testing and support for non-standard browsers and operating systems.
 - SVGs for graphics for default avatar/room pictures, iconography on the frontend.
 - Documentation clarification or correction, both in code and related markdown files.
 - User's guide and administrator's guide.
 - Support for more attachment backends.
 - Support for more authentication provider flows.
 - Native clients for mobile or desktop operating systems.
 - Changes that make custom integrations easier.

# Getting Started

At minimum, you will need a modern version of Python. Recommended version is 3.12 or
higher due to being tested only on this version, but some things in the repo also
depend on at least Python 3.11. Optionally, you will need a MySQL database or compatible
(MariaDB that is recent) that supports at least MySQL 5.7 features due to using the
JSON column type. If you do not have or want a MySQL database you can instead use
SQLite which comes built-in with Python. Finally, you will need ffmpeg installed for
notification conversion. For a production instance it is heavily recommended to use a
production-ready webserver for SSL termination and static resources such as nginx.

## Quick Start Guide

If you are on a modern debian-based operating system, you can run the following
commands in a terminal in order to get a basic version of CritterChat running in
as little time as possible:

```
# Install necessary system dependencies for CritterChat
sudo apt install python3 python3-dev python3-pip pkg-config \
         libmysqlclient-dev build-essential npm git ffmpeg just

# Check out CritterChat repo locally
git clone https://github.com/DragonMinded/critterchat.git
cd critterchat

# Setup python dependencies for your local configuration
just setup

# Initialize local configuration
just init
just manage database create

# Add a test user that you can use to log in with
just manage user create -u test -p test

# Add a test room that you will join when you log in
just manage room create -n "Test Room" -a on

# Run the frontend, which can be viewed at http://localhost:5678
just run
```

Once you've run those steps, you can go to [http://localhost:5678/](http://localhost:5678)
and login with username "test" and password "test" to start poking around.

## More Documentation

For in-depth documentation on development, please see [DEVELOPING.md](DEVELOPING.md).

For in-depth documentation on hosting a production instance, please see
[PRODUCTION.md](PRODUCTION.md).

For an administrator's manual, please see [ADMINISTRATION.md](ADMINISTRATION.md).
