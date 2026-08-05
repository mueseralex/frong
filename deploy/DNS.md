# frong.ai DNS (Cloudflare → Railway)

Add these records in the Cloudflare dashboard for zone **frong.ai**  
(DNS → Records). Prefer **DNS only** (grey cloud) for Railway custom domains.

## Apex `frong.ai`

| Type | Name | Content |
|------|------|---------|
| CNAME | `@` | `wv393zbo.up.railway.app` |
| TXT | `_railway-verify` | `railway-verify=4865600304204febb562baed4d228253876ee499fe2a8610501a2d86700d3f08` |

## `www.frong.ai`

| Type | Name | Content |
|------|------|---------|
| CNAME | `www` | `g9p7bn7c.up.railway.app` |
| TXT | `_railway-verify.www` | `railway-verify=27b570d25931adb055a3acd5de3672c4ac97aa6749ca99a33cf2ea0a97da91ad` |

After DNS propagates, Railway will issue certificates automatically.

Until then the site is live at: https://frong-production.up.railway.app
