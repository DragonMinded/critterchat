# Administration

Almost all of the administration for a CritterChat instance is done in the CLI using
the `critterchat.manage` package. For everything else, there are system-wide settings
in the config file you've configured for your instance. For a bare metal installation
the CLI can be accessed by activating your production virtual environment and then
running the following command:

```
python3 -m critterchat.manage --config <path to production config> --help
```

Alternatively, if you are using the just command runner in development you can run
the following to use your development setup to interact with your production instance:

```
just manage --config <path to production config> --help
```

For a docker installation you must first enter the production container using the
following command:

```
docker exec -it CritterChat /bin/sh
```

Then, once inside, you can use a variant of the above bare metal command like so:

```
python3 -m critterchat.manage --config config.yaml --help
```

All documented operations below will assume your chosen variant of the CLI command
above, specified by `<CLI>` in the example command invocation. Note that when
substituting your actual command for `<CLI>` you should leave out the `--help`
portion since that tells the management CLI to ignore the rest of the parameters
and instead print out help at the command-line.

All commands use angle bracket notation (`<>`) to denote spaces where you should
change the command to put in your own option. All command options should be a
whole word without spaces, so if you need to put spaces in an option make sure to
quote the option using double quotes (`""`).

## User Administration

Commands operating on users that are part of your instance are as follows. Note
that all of these commands are performed on behalf of the system instead of as
a particular account, so you can run these without first giving yourself the admin
permission. Note that every command you can run takes effect immediately.

### Listing Users

You can list out all users on the instance by using the following command:

```
<CLI> user list
```

This will show a list of all users, their permission (including activated status),
and their current instance nickname.

### Creating Users

Creating a new user is as simple as running the following command:

```
<CLI> user create -u <username> -p <password>
```

If you do not want to see the password, or you are running this locally for somebody
who wants to type in their own password, you can instead run the following variant
which will prompt for you to enter and re-enter a password at the command-line:

```
<CLI> user create -u <username>
```

If instead you want to give somebody a link to sign up on their own, you can
generate a one-time invite code by running the following command:

```
<CLI> user generate_invite
```

Note that if you configure your instance for open sign-ups, or closed sign-ups with
admin account activation, you won't need to create accounts from the CLI. Users can
click the "Create one!" link on the login page to create their own account.

### Activating and Deactivating Users

Activating a user that was created but not activated (or had been previously
deactivated by an administrator) can be done with the following command:

```
<CLI> user activate -u <username>
```

Deactivating a user rthat was previously active which you want to deactivate for
any reason can be done with the following command:

```
<CLI> user deactivate -u <username>
```

Note that this will immediately log the user out of any active chat sessions that
they are logged into. A deactivated user will be told that their account is not
active when attempting to log in.

### Changing User Passwords

You can change an existing user's password by running the following command:

```
<CLI> user change_password -u <username> -p <new password>
```

If you are running this command for a user or do not want to see the new password
you can instead run the following variant which will prompt for you to enter and
re-enter the new password at the command-line:

```
<CLI> user change_password -u <username>
```

If you instead want to give somebody a one-time password change URL so that they
can change their password remotely, you can run the following command to generate
a code:

```
<CLI> user generate_recovery -u <username>
```

### Managing Administrator Users

An administrator will get extra options on the web interface to mute and unmute
other users, deactivate or re-activate an account from the user's profile, set
or revoke room moderator access for users and change public room auto-join and
moderation settings. An administrator will also have access to create new public
rooms from the "find or start chat" dialog box.

If you want a specific user to be able to tweak these administration settings in
the web interface directly, you can run the following command to grant the admin
permission to a given user:

```
<CLI> user admin -u <username>
```

If you wish to revoke the admin permission for a given user you can run the following:

```
<CLI> user deadmin -u <username>
```

## Room Administration

Administration commands only take effect against public rooms. An administrator
gets no additional access to look at 1:1 messages or private conversations so the
following commands have no effect on those room types. Note that all commands require
a room ID which can be obtained by listing all public rooms first and then grabbing
the ID from the list.

### Listing Public Rooms

You can list out all public rooms on the instance by using the following command:

```
<CLI> room list
```

This will show a list of all public rooms along with the room's ID, name, topic
and room settings.

### Creating a new Public Room

You can create a new public room by running the following command:

```
<CLI> room create -n <room name> -t <room topic>
```

This will create a new public room that people can join by finding the room in the
"find or start chat" dialog box. You can set a room icon for the new room by including
the option `-c <path to icon file>`. You can set the room to be an auto-join room
(new users will auto-join the room after being activated, and existing users will be
added to the room upon creation) by including the option `-a on`. You can set the room
as a moderated room instead of a free-for-all room by including the option `-m on`.
Moderated rooms allow administrators to grant moderator status to users, and those
moderators can then mute users in the room. In a free-for-all room, only admins can
mute users.

### Modifying a Public Room

You can update a room's name, topic and icon by running the following command:

```
<CLI> room info -i <room ID> -n <new name> -t <new topic> -c <new icon path>
```

Note that you can leave out the name, topic or icon path option if you don't want
to change that particular bit of the room information.

To change a room's auto-join setting, run the following command, replacing on/off
with either "on" to enable or "off" to disable auto-join:

```
<CLI> room autojoin -i <room ID> -a <on/off>
```

Note that if you make a room auto-join that wasn't previously auto-join all users
on the instance who aren't in the room will be added to the room.

To change a room's moderated setting, run the following command, replacing on/off
with either "on" to set the room as moderated or "off" to set the room as a
free-for-all room:

```
<CLI> room moderated -i <room ID> -m <on/off>
```

### Modifying Moderators

For a room that is set as a moderated room, you can set a user as a moderator of
the room by running the following command:

```
<CLI> room grant_moderator -i <room ID> -u <username>
```

To revoke moderator status you can run the following:

```
<CLI> room revoke_moderator -i <room ID> -u <username>
```

Note that the user needs to be in the room for either of these commands to have
an effect. If the user in question is not in the room both commands will do nothing.

### Muting Users

You can mute a user in any public room by running the following command:

```
<CLI> room mute_user -i <room ID> -u <username>
```

That user will no longer be able to send any messages or change the room's information.
To unmute a user that was previously muted you can run the following command:

```
<CLI> room unmute_user -i <room ID> -u <username>
```

Note that in moderated rooms, users who have been muted by an administrator or by
the system at the CLI can still be unmuted by any active moderator in that room.

## Attachment Administration

Administrators do not have access to tamper with attachments added by anyone on
a given instance. At some point in the future there will be additional moderation
tools added which allow administrators to mark specific message attachments as
sensitive or even delete attachments that are against the instance's code of
conduct.

### Updating Default Icons

The default room icon, avatar image and instance icon can all be updated using
the following command, substituting the word "room", "avatar" or "favicon" in
place of room/avatar/favicon:

```
<CLI> attachment update -a <room/avatar/favicon> -f <path to new icon>
```

Note that if you want to revert a given image back to the default that ships
with CritterChat you can give the option `-f default` instead of giving the
command a specific path.

### Listing Custom Emotes

To list all custom emotes that have been added to your instance, you can run
the following command:

```
<CLI> emote list
```

### Adding a new Emote

To add a new custom emote to the instance, you can run the following command:

```
<CLI> emote import -f <path to emote file>
```

This will add the emote to the instance and infer the emote name based on the file
name of the emote. For instance, if you added the emote "spraybottle.jpg" to your
instance with this command, users could access the emote by typing ":spraybottle:".
If you want to specify a custom alias you can add the option `-a <alias>` to the
command. Note that emote aliases must be letters, numbers, dashes and underscores only.

If you want to add an entire directory of emotes to the instance at once, you can
run the same command but give a path to the directory. CritterChat will find all
images inside that directory and add them as emotes, using the filename as the alias.
This way you can import entire emote packs by unzipping them and adding the directory.

Note that in both the single emote and directory cases, emotes that already exist on
the instance will be skipped. If you want to change an emote, you must first remove
the existing emote and then add the new image with the same alias.

### Removing an Existing Emote

To remove an existing emote from the instance, you can run the following command:

```
<CLI> emote remove -a <alias>
```

You can get the alias of an emote by listing custom emotes documented above.

### Exporting Existing Emotes

You can export all existing emotes to a directory by running the following command:

```
<CLI> emote export -d <directory to export to>
```

This will create the directory if it doesn't exist and then write out all emotes
as image files in that directory, named after the emote alias. You can use this, for
instance, to export all emotes from one instance you administer and then import them
all on another instance.

## Authentication Administration

Authentication is mostly controlled via your configuration file. Inside your
configuration yaml you should find an "authentication" section which contains
all of the below documented authentication options.

### Local Authentication

You can disable local authentication (logging in with a username and password)
by setting the "local" setting to "false" instead of "true". When local authentication
is disabled the only way that users can log in is with configured OAuth providers.
When local authentication is enabled then uesrs can log in with any configured
OAuth provider or by using a username and password combo that they've previously
created or been given by an administrator.

### Mastodon Instance Authentication

You can enable one or more Mastodon instances to act as an OAuth provider to
log in to your instance. By adding an instance to the "mastodon" setting you can
add a button to the login screen allowing users to authenticate using that instance.
You can also configure whether new accounts created via Mastodon OAuth auto-set
the user's profile information (nickname, icon and profile details) based on the
user's account on the Mastodon instance by setting the "copy_profile" setting for
a given instance to "true" to allow auto-setting, or "false" to disallow it. Note
that even with this setting on, once a user's account has been created on your
instance, if the user changes their details on Mastodon those details will not
be reflected on your instance.

Note that it is not sufficient to list one or more instances in your config yaml.
You also need to register your CritterChat instance with all of the Mastodon
instances you've configured. You can do so with the following command:

```
<CLI> mastodon register
```

If you want to register with only one specific instance you can add the option
`-i <URL of instance>` to the command.

To list out all instances and their registered status, you can run the following:

```
<CLI> mastodon list
```

If you want to unlink your CritterChat instance from a specific Mastodon instance
to stop allowing people to use it for login, you can run the following command:

```
<CLI> mastodon unregister -i <URL of instance>
```

Only registered and connected Mastodon instances will be presented as options for
users to log in with.

## Sign-Up Administration

All sign-up settings are administered through the config yaml that you've customized
for the instance you're running. You can find all of the below documented settings
under the "account_registration" section in your configuration file.

### Enabling Local Sign-Ups

If you want users to be able to create accounts locally using the "Create one!" link
on the login page, you should leave the "enabled" setting set to "true". If you want
to disable self-created accounts, you can change the "enabled" setting to "false".
Note that disabling local sign-ups does not disable local authentication entirely.
Users can still login using a username and password if an administrator created an
account for them or if they signed up using an invite link. Users can also create
an account by signing in through any active Mastodon instance that they haven't
linked to a local account yet.

### Enabling Auto-Approval

If you want users who have signed up through the "Create one!" new account flow to
be activated automatically you can set the "auto_approve" setting to "true". Note
that this could allow people to flood your instance so it is disabled by default.
If this is set to "false" then users who self-create local accounts will need to
wait for an administrator to activate their account. Note also that this setting
does not affect accounts created by logging in through a connected Mastodon instance.
Note also that accounts created through invite links will be auto-approved even
with this setting disabled.

### Enabling Invites

If you want users who are already active on your instance to be able to invite other
people to chat, you can enable invites by setting the "invites" setting to "true".
If this is enabled, everyone will get an "invite somebody" button on their chat
interface next to the "find or start chat" button that they can use to invite friends
to chat. People who sign up through invites are auto-approved. If this is disabled
then the only people who can generate invite links are administrators.

## Instance Limit Administration

All instance limits are administered through the config yaml that you've customized
for your instance. You can find all of the below documented settings underneath the
"limits" section in your configuration file.

### Message Limits

You can control how many characters long a user's profile is allowed to be using the
"about_length" setting. If not provided, this defaults to 64000 characters. You can
control how long a message can be using the "message_length" setting, which defaults
to 64000 characters as well. You can also control how long an attachment's alt text
can be using the "alt_text_length" setting which defaults to 64000 characters if not
set.

### Attachment Limits

You can control how many attachments can be attached to a given message using the
"attachment_max" setting. If you want to disable attachments on messages entirely
you can set this setting to "0". This will disable the attachment button on the message
composer but it will not remove any existing attachments on messages already present.
You can set the maximum size in kilobytes (KB) of a given user or room's custom icon
by changing the "icon_size" setting which defaults to 128 KB if not modified. You can
change the maximum size in kilobytes of a user's custom notification sound by changing
the "notification_size" setting which defaults to 128 KB if not modified. You can
change the maximum size in kilobytes of a given message attachment by modifying the
"attachment_size" setting which defaults to 2048 KB (2 MB) if not modified.
