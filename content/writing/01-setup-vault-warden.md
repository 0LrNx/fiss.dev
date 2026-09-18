+++
title = "Vaultwarden installation guide"
date = 2026-09-18
description = "A complete writeup on installing Vaultwarden, from the basic setup to certificates, a custom domain, and backups."

[extra]
cover = "images/image.webp"
+++

![Alt text](/images/image.webp)

---

This article explains how to set up Vaultwarden properly — covering security, accessibility, and maintenance.

## Overview & why

The goal of this setup is to **own** and **control** your passwords.

By 2026 I'd hope everyone uses a password manager to generate and store strong credentials. But a strong password is worth nothing if the vault holding it belongs to someone else: you're trusting a third party with the keys to everything.

Self-hosting solves that. Vaultwarden is a lightweight reimplementation of the Bitwarden server, written in Rust — it runs comfortably on a Raspberry Pi and stays compatible with all the official Bitwarden clients.

One thing worth understanding up front: **your vault is encrypted client-side**. The server only ever stores an encrypted blob. Even if someone compromised the machine, they'd get ciphertext, not passwords. That's what makes exposing Vaultwarden to the internet an acceptable risk — unlike, say, exposing a NAS.

Here's the architecture we'll build:

![Vaultwarden schema setup](/images/schema-vaultwarden-setup.png)

### Requirement 

- A domain name (mine is registered at Infomaniak)
- A machine that stays on (VPS, server, or Raspberry Pi)
- Docker and Docker Compose installed
- Time and a good coffee

### A note on network access

Before going further, check whether you can actually open ports on your router:

```bash
curl -s https://api.ipify.org
```

Compare that with the WAN address shown in your router's admin interface. If they differ (typically a `100.64.x.x` address on the router side), you're behind **CGNAT** and port forwarding will never work, no matter what your ISP's support tells you. This is common on French ISPs like SFR.


## Install a client

Install the Bitwarden client for your platform — desktop app, browser extension, or mobile. Vaultwarden speaks the same API, so the official clients work unchanged.

[Download](https://bitwarden.com/fr-fr/download/#downloads-desktop-applications)

Set it aside for now; we'll point it at the self-hosted server once it's running.

## Docker network

Every service below lives in its own Compose file but needs to talk to the others. Create a shared external network once:

```bash
docker network create web
```

Declaring it as `external: true` in each Compose file means Docker won't create or destroy it on `up`/`down` — the network outlives any individual project.


## Vaultwarden setup

Check the [official repository](https://github.com/dani-garcia/vaultwarden) for other installation methods, but Docker Compose is the simplest.

```bash
mkdir vaultwarden && cd vaultwarden
nano compose.yaml
```


```yaml
services:
  vaultwarden:
    image: vaultwarden/server:latest
    container_name: vaultwarden
    restart: unless-stopped
    environment:
      DOMAIN: "https://vw.domain.tld"
    volumes:
      - ./vw-data/:/data/
    ports:
      - 127.0.0.1:8000:80
```

Two things to note:

- **No `ports:` mapping.** Vaultwarden is never exposed on the host. The reverse proxy reaches it through the Docker network on port 80. Publishing a port here would only widen the attack surface.
- **`DOMAIN` must be the real public URL.** Vaultwarden uses it for WebAuthn/passkeys and for links in emails. Getting it wrong breaks 2FA with security keys in confusing ways.

`SIGNUPS_ALLOWED` stays `true` just long enough to create your own account — we close it at the end.

```bash
docker compose up -d
```

## Reverse proxy: nginx-proxy-manager

```bash
mkdir nginx-proxy-manager && cd nginx-proxy-manager
nano docker-compose.yml
```

```yaml
services:
  npm:
    image: jc21/nginx-proxy-manager:latest
    container_name: nginx-proxy-manager
    restart: unless-stopped
    ports:
      - '80:80'
      - '81:81'
      - '443:443'
    volumes:
      - npm_data:/data
      - npm_letsencrypt:/etc/letsencrypt
    networks:
      - web

volumes:
  npm_data:
  npm_letsencrypt:

networks:
  web:
    external: true
```

```bash
docker compose up -d
```

**Port 81 is the admin interface — never expose it to the internet.** Keep it reachable only from your LAN or over a VPN.

### First login

Open `http://<server-ip>:80`. Recent NPM versions (2.14+) drop the old `admin@example.com` / `changeme` default and ask you to create an account on first run. Write the password down before submitting it.

### Proxy host

**Hosts → Proxy Hosts → Add Proxy Host**, tab *Details*:

- Domain Names: `vault.domain.tld`
- Scheme: `http`
- Forward Hostname / IP: `vaultwarden`
- Forward Port: `80`
- **Websockets Support: on** — Vaultwarden needs it for live sync between devices
- Block Common Exploits: on

The hostname is literally `vaultwarden`, not an IP: Docker resolves container names on the shared `web` network.

### Certificate via DNS challenge

The usual HTTP-01 challenge requires Let's Encrypt to reach your server on port 80 — impossible behind CGNAT. Use **DNS-01** instead: validation happens through a TXT record on your domain, so no inbound connectivity is needed.

In the *SSL* tab: **Request a new SSL Certificate**, tick **Use a DNS Challenge**. Infomaniak isn't in NPM's dropdown, but NPM ships `acme.sh`, which supports it. Pick **Other** and fill in:

- DNS Provider: `dns_infomaniak`
- Credentials File Content: `INFOMANIAK_ACCESS_TOKEN=your_token`
- Propagation Seconds: `120`

The token comes from the Infomaniak Manager: avatar → **My account** → **Developer** → API token, scope **Domain**, unlimited lifetime (a token that expires will silently break renewals). It's shown once — copy it immediately.

Tick **Force SSL** and **HTTP/2 Support**, accept the Let's Encrypt terms, and save.


## Cloudflare Tunnel

The tunnel is what makes this reachable without opening a single port. `cloudflared` runs on your machine and opens an **outbound** connection to Cloudflare, which then becomes the public entry point. Traffic never has to get *into* your network — your machine goes out to fetch it.

### Move DNS to Cloudflare

Create a free Cloudflare account, then **Add domain** → your domain → **Free** plan. Cloudflare imports your existing records — check them carefully, especially MX records if you receive mail on that domain. A missing MX is the classic way to lose email for a day.

Delete any `A` record pointing at your old public IP; the tunnel will create its own `CNAME` and the two can't coexist on the same name.

Cloudflare then gives you two nameservers. At Infomaniak: **Domains** → your domain → **DNS servers**. You'll first have to disable *DNS Fast Anycast* (Infomaniak's own DNS service, incompatible with external nameservers), then replace the Infomaniak nameservers with Cloudflare's.

You keep owning the domain at Infomaniak — only the DNS zone moves. Propagation takes anywhere from 15 minutes to a few hours:

```bash
nslookup -type=ns domain.tld 1.1.1.1
```

### Create the tunnel

Once Cloudflare marks the domain **Active**: **Zero Trust → Networks → Tunnels → Create a tunnel → Cloudflared**.

Cloudflare asks for a payment method to activate Zero Trust, **even on the free plan**. It's an anti-abuse check and you won't be charged, but if that's a dealbreaker there's a CLI-based alternative (`cloudflared tunnel login`) that skips Zero Trust entirely, at the cost of the web UI and Cloudflare Access.

Name the tunnel, then copy the token it hands you.

```bash
mkdir cloudflared && cd cloudflared
nano docker-compose.yml
```

```yaml
services:
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: cloudflared
    restart: unless-stopped
    command: tunnel --no-autoupdate run
    environment:
      TUNNEL_TOKEN: "your_tunnel_token"
    networks:
      - web

networks:
  web:
    external: true
```

```bash
docker compose up -d
docker compose logs -f
```

The tunnel should show as **HEALTHY** in the dashboard.

### Route traffic

In the tunnel, go to **Published application routes** (not *Hostname routes*, which handle private routing inside your Cloudflare network):

- Subdomain: `vault`
- Domain: `domain.tld`
- Type: `HTTP`
- URL: `nginx-proxy-manager:80`

Cloudflare creates the matching `CNAME` automatically.

> **Is NPM still needed?** Honestly, for a single service, not really — the tunnel could point straight at `vaultwarden:80`. I kept it because I plan to host more services behind the same machine, and NPM gives me one place to manage them. If Vaultwarden is all you'll ever run, you can drop it and simplify.


### Trade-off to be aware of

Cloudflare terminates TLS, which means it sees your traffic in plaintext before re-encrypting it to your machine. For Vaultwarden specifically this is acceptable: the vault contents are encrypted client-side, and your master password never leaves the browser. Cloudflare sees metadata — URLs, timing — not secrets. If that still bothers you, a small VPS relay over WireGuard keeps everything under your control for a few euros a month.


## Hardening

Now that it's publicly reachable, lock it down.

**Create your account**, then close registration in `compose.yaml`:

```yaml
environment:
  DOMAIN: "https://vault.domain.tld"
  SIGNUPS_ALLOWED: "false"
```

```bash
docker compose up -d --force-recreate
```

**Enable 2FA** immediately — Settings → Security → Two-step login. TOTP or a hardware key. This is your real defence.

**Leave the admin panel disabled.** Without `ADMIN_TOKEN`, `/admin` returns a message and nothing else. If you ever need it, put it behind Cloudflare Access rather than relying on the token alone.

**Keep images updated** — `docker compose pull && docker compose up -d`.


## Backups (the most important part)

Everything above is worthless if the SD card dies. And SD cards die.

What matters lives in `vw-data/`:

- `db.sqlite3` — the vault itself
- `rsa_key.pem` / `rsa_key.pub.pem` — without these, a restored database is useless
- `attachments/` and `sends/`

Don't just `cp` the database. SQLite may be mid-write, and you'd end up with a corrupt file that looks fine until the day you need it. Use SQLite's own backup command:

```bash
docker exec vaultwarden sqlite3 /data/db.sqlite3 ".backup '/data/backup.sqlite3'"
```

A simple script, run daily from cron:

```bash
#!/bin/bash
set -e
SRC="$HOME/vaultwarden/vw-data"
DEST="/mnt/backup/vaultwarden"
STAMP=$(date +%Y%m%d)

docker exec vaultwarden sqlite3 /data/db.sqlite3 ".backup '/data/backup.sqlite3'"
mkdir -p "$DEST"
tar czf "$DEST/vw-$STAMP.tar.gz" -C "$SRC" backup.sqlite3 rsa_key.pem rsa_key.pub.pem attachments sends 2>/dev/null
rm -f "$SRC/backup.sqlite3"
find "$DEST" -name 'vw-*.tar.gz' -mtime +30 -delete
```

0 3 * * * /home/user/backup-vault.sh

Send the archive somewhere off the machine — rsync to a NAS, a remote server, or encrypted object storage. A backup sitting on the same SD card isn't a backup.

**Test your restore at least once.** An untested backup is a hypothesis.

As a second line of defence, the web vault can export an encrypted copy (Tools → Export vault). Keep it somewhere safe; it's independent of any Docker or filesystem problem.

## Wrapping up

You now have a password manager on your own hardware, reachable from anywhere over HTTPS with your own domain, with no open ports and no VPN requirement.

The parts that actually matter, in order: your master password (nobody can recover it), your 2FA, and your backups.
