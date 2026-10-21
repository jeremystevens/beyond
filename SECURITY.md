# Security policy

BEYOND runs on your own PC and can be opened from other devices on your network, or over the internet, with a
sign-in. It also stores your chats and memories and can write files. Security problems matter here, and reports
are very welcome.

## Reporting a vulnerability

**Please don't report security problems in a public issue, discussion or pull request.**

Report them privately instead:

1. Go to the repository's **Security** tab.
2. Choose **Report a vulnerability**. This uses GitHub's private vulnerability reporting, so only the maintainer
   can see it.

Please include:

- what the problem is, and what someone could do with it;
- the BEYOND version (shown on the Status page or at `/api/health`) and your Windows version;
- the steps to reproduce it, and which settings are needed (for example "Allow other devices" on, or sign-in off);
- a proof of concept, if you have one.

Please **don't** include real passwords, session cookies, personal chats or other people's data.

## What happens next

- You'll get a reply within **7 days** saying whether the report is confirmed.
- A confirmed problem is fixed as quickly as its seriousness calls for, and you'll be kept up to date.
- Once a fix is released, it's noted in the changelog. You're credited if you'd like to be.

Please give the fix a reasonable time to ship before telling anyone else about the problem.

## Supported versions

BEYOND is in active development and doesn't have long-term support releases yet. Fixes go into the latest version
on `main`. Please check that the problem still happens there before reporting it.

## Especially welcome reports

- Getting past the sign-in, or getting administrator access without the administrator password
- Changing settings, downloading models or reading, writing or editing files from another device without
  permission
- Reading or writing files outside BEYOND's own folders (`data\`, `models\`, `files\`)
- Text from a web page, a file or the AI making BEYOND run commands or act against the user's wishes
- Anything that sends the user's chats, memories or files somewhere they didn't ask for

## Keeping your own BEYOND safe

- Leave **Allow other devices on my network** off unless you need it.
- If other devices use BEYOND, keep **Require other devices to sign in** on, and use long, different passwords for
  sign-in and the administrator.
- Over the internet, always use the `https://` address (port 7771), never plain `http://`.
- Keep BEYOND up to date.
