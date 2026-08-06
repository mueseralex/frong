# Give the agent Cloudflare access (2 minutes)

Do **one** of these. Option A is enough for DNS.

## Option A — API token (best for DNS)

1. Open https://dash.cloudflare.com/profile/api-tokens  
2. **Create Token** → use template **Edit zone DNS**  
3. Zone Resources → **Include** → Specific zone → **frong.ai**  
4. Create token → copy it once  
5. Paste it back in chat as:

```
CLOUDFLARE_API_TOKEN=...
```

(Or save to `~/.frong/cloudflare.env` as `CLOUDFLARE_API_TOKEN=...` and tell me it’s there.)

I’ll then create the Railway CNAME + verify TXT records automatically.

## Option B — cloudflared cert (tunnels)

A browser window should already be open for Cloudflare Tunnel authorize.

1. Log into the Cloudflare account that owns **frong.ai**  
2. Select the **frong.ai** zone when asked  
3. Authorize  

That writes `~/.cloudflared/cert.pem` so named tunnels / DNS routing work.

## Manual fallback (no token)

In Cloudflare → **frong.ai** → DNS → add (DNS only / grey cloud):

| Type | Name | Content |
|------|------|---------|
| CNAME | `@` | `wv393zbo.up.railway.app` |
| TXT | `_railway-verify` | `railway-verify=4865600304204febb562baed4d228253876ee499fe2a8610501a2d86700d3f08` |
| CNAME | `www` | `g9p7bn7c.up.railway.app` |
| TXT | `_railway-verify.www` | `railway-verify=27b570d25931adb055a3acd5de3672c4ac97aa6749ca99a33cf2ea0a97da91ad` |
