# oscopy

Python script to copy from STD to your clipboard with OSC 52.

## How to Use It

You simply pipe to it, then you can paste whatever you piped:

```bash
echo coucou_yopta | oscopy
# now you can paste "coucou_yopta" everywhere
```

> [!IMPORTANT]
> This works even if you're connected to a remote SSH server. The content will travel through SSH and arrive in your local system clipboard.

Attention though, the `echo` adds a trailing newline. You can strip it with `oscopy -s`:

```bash
echo precision | oscopy -s
# now you can paste "precision" knowing it won't add a newline
```

Why not piping file contents?

```bash
cat ~/.ssh/id_rsa.pub | oscopy -s
# then paste your SSH pubkey on the website...
```

If you want you can just pass your text as args, not piping anything:

```bash
oscopy Yes, I can do this.
# this makes "Yes, I can do this." magically appear in your clipboard
```

## Install

Install as an [`uv` tool](https://docs.astral.sh/uv) from this GitHub repo:

```bash
uv tool install git+https://github.com/hammerill/oscopy
```

Or local dev install:

```bash
# in oscopy project folder
uv tool install -e .
```
