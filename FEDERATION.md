Collection of thoughts around federation design.

 - Want an instance to be akin to a discord server. Thus, its important that to get the correct experience, you join an instance to get added to their public channels as well as their MOTD/rules/etc.
 - Still want "federation" in that your home instance allows you to chat in private 1:1s as well as private group chats with other servers.
 - Seems like a hybrid approach is necessary where instances federate for private messages, but also allow SSO from your home instance for signing up/onto other instances.
 - If you wanted to join and you already had a home instance, you'd sign in through that and it would make your account as account@home.instance.domain isntead of just account. You'd still interact with that instance as if you were signed in locally, but your account would be homed on another instance.
 - If you wanted to DM someone from another instance, but didn't have an account on that instance, it would use entirely federation.
 - If you were logged into that instance and DM'd somebody it would appear local. Does this work? What if you log into something remotely and then DM somebody who is logged in to another server remotely?
 - Each instance shows you the "view" of being on that instance if you logged into it.
 - Your home instance is where all DMs and group chats are visible, as well as any public channels on that home instance you're in.

How to make this seamless for most people? How to make it so that it doesn't matter what the distinction is? Probably when you SSO your home server starts tracking that server for federation, so anyone you DM when logged in there shows up on your home instance. Will need a "sign in with home instance" flow on the main screen, and an SSO flow on your home instance. Not sure if a global value can be set in the browser to alert users to this possibility? Probably not, and would get abused for tracking likely? How to relay the concept of a "home server". Do we want the ability to transfer home servers? How to reconcile if that gets out of sync?

Needs a lot of additional thought and design mulling.
