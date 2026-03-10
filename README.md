# oscopy

Python tool to copy text to your local clipboard over OSC 52, and record shell command transcripts.

## How to Use It

### Piping

You simply pipe to `oscopy`, then paste anywhere:

```bash
echo coucou_yopta | oscopy
# now you can paste "coucou_yopta" everywhere
```

> [!IMPORTANT]
> This works even if you're connected to a remote SSH server. The content travels through SSH and arrives in your local system clipboard.

`echo` adds a trailing newline. Strip it with `-s` (or `-x`):

```bash
echo precision | oscopy -s
# now you can paste "precision" knowing it won't add a newline
```

Why not piping file contents?

```bash
cat ~/.ssh/id_rsa.pub | oscopy
# then paste your SSH pubkey on the website...
```

### Record a Command

If you need to execute something and copy both the command you typed and whatever it returned back, e.g.:

```bash
$ ls -la
total 112
drwxr-xr-x@ 11 hammerill  staff    352 Mar 10 12:48 .
drwxr-xr-x  12 hammerill  staff    384 Mar  2 11:59 ..
drwxr-xr-x@ 15 hammerill  staff    480 Mar 10 15:36 .git
-rw-r--r--@  1 hammerill  staff    109 Feb  5 09:31 .gitignore
-rw-r--r--@  1 hammerill  staff      5 Feb  5 09:31 .python-version
drwxr-xr-x@  8 hammerill  staff    256 Feb  5 09:31 .venv
-rw-r--r--@  1 hammerill  staff  35149 Feb  5 09:31 LICENSE
-rw-r--r--@  1 hammerill  staff    390 Feb  5 09:31 pyproject.toml
-rw-r--r--@  1 hammerill  staff   1753 Mar 10 13:16 README.md
drwxr-xr-x@  3 hammerill  staff     96 Feb  5 09:31 src
-rw-r--r--@  1 hammerill  staff    127 Feb  5 09:31 uv.lock
```

...you can use oscopy to do this quickly:

```bash
oscopy run ls -la
# now you can paste the thing from above
```

You can try any other Shell command:

```bash
oscopy run -- git status --short
```

`--` is optional, but useful to avoid ambiguity in edge cases with CLI args.

### Record a Shell Session

Start a temporary recording shell:

```bash
oscopy record
# or `oscopy start`
```

Session mode currently runs in a temporary `zsh` shell.

Then run commands normally. When done:

```bash
oscopy stop
```

This copies a transcript like:

```bash
$ ls *.md
-rw-r--r--@ 1 hammerill  staff   1.1K Mar 10 12:48 README.md

$ uname -a
Darwin pommier 25.3.0 Darwin Kernel Version 25.3.0 ...
```

The transcript uses `$ ` as the command prefix, includes both stdout and stderr, and inserts clean blank lines between commands.

## Install

Install as a [uv tool](https://docs.astral.sh/uv) from this GitHub repo:

```bash
uv tool install git+https://github.com/hammerill/oscopy
```

Or local dev install:

```bash
# in oscopy project folder
uv tool install -e .
```
